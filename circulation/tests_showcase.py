from datetime import timedelta
from decimal import Decimal
from io import StringIO
import secrets

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import MemberProfile, User
from books.models import Book, Category
from circulation.models import BorrowRecord, BorrowRequest, Fine

FAST_HASHER = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


def make_member(username, max_books=3):
    user = User.objects.create_user(
        username=username, password=secrets.token_urlsafe(8), role=User.ROLE_MEMBER
    )
    MemberProfile.objects.create(
        user=user, membership_id=f"MEM-{username}", max_books_allowed=max_books
    )
    return user


def make_staff(username="staff1"):
    return User.objects.create_user(
        username=username, password=secrets.token_urlsafe(8), role=User.ROLE_STAFF, is_staff=True
    )


def make_book(isbn, title="Book", copies=2, category=None):
    return Book.objects.create(
        title=title, author="Author", isbn=isbn, total_copies=copies,
        available_copies=copies, category=category,
    )


@FAST_HASHER
class BorrowingWorkflowTests(TestCase):
    def setUp(self):
        self.staff = make_staff()
        self.member = make_member("alice")
        self.book = make_book("1111111111111", "Algorithms", copies=2)

    def request_book(self, user, book, days=5):
        self.client.force_login(user)
        return self.client.post(
            reverse("circulation:create_request", args=[book.pk]), {"requested_days": days}
        )

    def approve(self, req):
        self.client.force_login(self.staff)
        return self.client.post(reverse("circulation:approve_request", args=[req.pk]))

    def return_loan(self, record, days_after_issue=None):
        self.client.force_login(self.staff)
        return_date = timezone.now().date()
        return self.client.post(
            reverse("circulation:return_book", args=[record.pk]), {"return_date": return_date}
        )

    def test_full_cycle_and_rerequest_after_return(self):
        self.request_book(self.member, self.book)
        req = BorrowRequest.objects.get()
        self.assertEqual(req.status, BorrowRequest.STATUS_PENDING)

        self.approve(req)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)
        record = BorrowRecord.objects.get()
        self.assertEqual(record.status, BorrowRecord.STATUS_ISSUED)

        self.return_loan(record)
        self.book.refresh_from_db()
        record.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)
        self.assertEqual(record.status, BorrowRecord.STATUS_RETURNED)
        self.assertTrue(Fine.objects.filter(borrow_record=record).exists())

        # The old APPROVED request must not block a fresh request for the same title.
        self.request_book(self.member, self.book)
        self.assertEqual(BorrowRequest.objects.filter(status=BorrowRequest.STATUS_PENDING).count(), 1)
        self.client.force_login(self.member)
        detail = self.client.get(reverse("books:book_detail", args=[self.book.pk]))
        self.assertContains(detail, "Request Pending")

    def test_duplicate_pending_request_rejected(self):
        self.request_book(self.member, self.book)
        self.request_book(self.member, self.book)
        self.assertEqual(BorrowRequest.objects.count(), 1)

    def test_unavailable_book_cannot_be_requested(self):
        self.book.available_copies = 0
        self.book.save()
        self.request_book(self.member, self.book)
        self.assertEqual(BorrowRequest.objects.count(), 0)

    def test_profile_limit_enforced_on_request_and_approval(self):
        limited = make_member("limited", max_books=1)
        other = make_book("2222222222222", "Networks")
        third = make_book("3333333333333", "Databases")
        self.request_book(limited, self.book)
        self.request_book(limited, other)  # second pending request allowed; limit hits at approval
        first, second = BorrowRequest.objects.order_by("pk")
        self.approve(first)
        self.approve(second)
        second.refresh_from_db()
        self.assertEqual(second.status, BorrowRequest.STATUS_PENDING)
        self.assertEqual(BorrowRecord.objects.filter(member=limited).count(), 1)

        self.request_book(limited, third)
        self.assertFalse(BorrowRequest.objects.filter(book=third).exists())

    def test_reject_leaves_inventory_untouched(self):
        self.request_book(self.member, self.book)
        req = BorrowRequest.objects.get()
        self.client.force_login(self.staff)
        self.client.post(reverse("circulation:reject_request", args=[req.pk]))
        req.refresh_from_db()
        self.book.refresh_from_db()
        self.assertEqual(req.status, BorrowRequest.STATUS_REJECTED)
        self.assertEqual(self.book.available_copies, 2)

    def test_double_approval_issues_only_once(self):
        self.request_book(self.member, self.book)
        req = BorrowRequest.objects.get()
        self.approve(req)
        self.approve(req)
        self.assertEqual(BorrowRecord.objects.count(), 1)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)

    def test_manual_issue_does_not_close_unrelated_request(self):
        other_member = make_member("bob")
        self.request_book(other_member, self.book)
        req = BorrowRequest.objects.get()
        self.client.force_login(self.staff)
        today = timezone.now().date()
        self.client.post(reverse("circulation:issue_book"), {
            "member": self.member.pk, "book": self.book.pk, "issue_date": today,
            "requested_days": 7, "request_id": req.pk,
        })
        req.refresh_from_db()
        self.assertEqual(req.status, BorrowRequest.STATUS_PENDING)
        self.assertEqual(BorrowRecord.objects.filter(member=self.member).count(), 1)

    def test_return_date_cannot_be_future(self):
        self.request_book(self.member, self.book)
        self.approve(BorrowRequest.objects.get())
        record = BorrowRecord.objects.get()
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("circulation:return_book", args=[record.pk]),
            {"return_date": timezone.now().date() + timedelta(days=3)},
        )
        self.assertEqual(response.status_code, 200)
        record.refresh_from_db()
        self.assertEqual(record.status, BorrowRecord.STATUS_ISSUED)

    def test_late_return_fee_matches_policy_function(self):
        today = timezone.now().date()
        self.book.available_copies = 1
        self.book.save()
        record = BorrowRecord.objects.create(
            book=self.book, member=self.member, issued_by=self.staff,
            issue_date=today - timedelta(days=6), due_date=today - timedelta(days=3),
            requested_days=3,
        )
        self.return_loan(record)
        fine = Fine.objects.get(borrow_record=record)
        self.assertEqual(fine.duration_days, 6)
        self.assertEqual(fine.overdue_days, 3)
        self.assertEqual(fine.amount, BorrowRecord.calculate_borrowing_fee(6))
        self.assertFalse(fine.is_paid)


@FAST_HASHER
class CatalogueTests(TestCase):
    def setUp(self):
        self.staff = make_staff()
        self.cs = Category.objects.create(name="Computer Science")
        self.lit = Category.objects.create(name="Literature")
        for i in range(20):
            make_book(f"97800000000{i:02d}", f"Title {i:02d}", copies=1, category=self.cs)
        self.hyphenated = make_book("978-0-13-235088-4", "Clean Code", category=self.lit)
        self.hyphenated.author = "Robert Martin"
        self.hyphenated.save()
        self.client.force_login(self.staff)

    def test_isbn_search_ignores_hyphens(self):
        for term in ("9780132350884", "978-0-13-235088-4"):
            response = self.client.get(reverse("books:book_list"), {"q": term})
            self.assertContains(response, "Clean Code")

    def test_author_and_availability_filters(self):
        response = self.client.get(reverse("books:book_list"), {"q": "Martin"})
        self.assertContains(response, "Clean Code")
        Book.objects.filter(pk=self.hyphenated.pk).update(available_copies=0)
        response = self.client.get(reverse("books:book_list"), {"availability": "available", "q": "Clean"})
        self.assertNotContains(response, "Clean Code")

    def test_pagination_preserves_encoded_filters(self):
        response = self.client.get(
            reverse("books:book_list"), {"category": self.cs.pk, "q": "Title", "sort": "author"}
        )
        self.assertEqual(len(response.context["books"]), 15)
        self.assertIn("q=Title", response.context["filter_querystring"])
        page2 = self.client.get(
            reverse("books:book_list") + "?page=2&" + response.context["filter_querystring"]
        )
        self.assertEqual(len(page2.context["books"]), 5)

    def test_invalid_category_and_sort_are_ignored(self):
        response = self.client.get(reverse("books:book_list"), {"category": "abc", "sort": "bogus"})
        self.assertEqual(response.status_code, 200)

    def test_edit_cannot_corrupt_inventory(self):
        member = make_member("carol")
        today = timezone.now().date()
        book = self.hyphenated
        book.total_copies = 3
        book.available_copies = 3
        book.save()
        for username in ("carol", "dave"):
            BorrowRecord.objects.create(
                book=book, member=make_member(username) if username != "carol" else member,
                issued_by=self.staff, issue_date=today, due_date=today + timedelta(days=7),
            )
        book.available_copies = 1
        book.save()

        payload = {
            "title": book.title, "author": book.author, "isbn": book.isbn,
            "total_copies": 1, "language": "English", "book_value": "500",
        }
        response = self.client.post(reverse("books:book_edit", args=[book.pk]), payload)
        self.assertEqual(response.status_code, 200)

        payload["total_copies"] = 5
        self.client.post(reverse("books:book_edit", args=[book.pk]), payload)
        book.refresh_from_db()
        self.assertEqual((book.total_copies, book.available_copies), (5, 3))

    def test_delete_book_with_history_is_handled(self):
        member = make_member("erin")
        today = timezone.now().date()
        BorrowRecord.objects.create(
            book=self.hyphenated, member=member, issued_by=self.staff, issue_date=today,
            due_date=today, return_date=today, status=BorrowRecord.STATUS_RETURNED,
        )
        response = self.client.post(reverse("books:book_delete", args=[self.hyphenated.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Book.objects.filter(pk=self.hyphenated.pk).exists())


@FAST_HASHER
class DashboardAccuracyTests(TestCase):
    def test_counts_reflect_database(self):
        staff = make_staff()
        member = make_member("frank")
        book = make_book("4444444444444", copies=3)
        today = timezone.now().date()
        BorrowRecord.objects.create(
            book=book, member=member, issued_by=staff,
            issue_date=today - timedelta(days=10), due_date=today - timedelta(days=3),
        )
        book.available_copies = 2
        book.save()
        BorrowRequest.objects.create(member=member, book=book, requested_days=5)

        self.client.force_login(staff)
        ctx = self.client.get(reverse("dashboard:staff_dashboard")).context
        self.assertEqual(ctx["overdue_books_count"], 1)
        self.assertEqual(ctx["issued_books_count"], 1)
        self.assertEqual(ctx["pending_requests_count"], 1)
        self.assertEqual(ctx["total_available_copies"], 2)
        self.assertEqual(ctx["pending_fines_sum"], Decimal("0.00"))

        self.client.force_login(member)
        mctx = self.client.get(reverse("dashboard:member_dashboard")).context
        self.assertEqual(mctx["current_loans_count"], 1)
        self.assertEqual(mctx["overdue_count"], 1)
        self.assertEqual(mctx["pending_requests_count"], 1)


@FAST_HASHER
class SeedDemoTests(TestCase):
    def setUp(self):
        for i in range(12):
            make_book(f"90000000000{i:02d}", f"Seed {i}", copies=3)

    def test_idempotent_and_inventory_consistent(self):
        call_command("seed_demo", password=secrets.token_urlsafe(12), stdout=StringIO())
        snapshot = (
            User.objects.count(), BorrowRequest.objects.count(),
            BorrowRecord.objects.count(), Fine.objects.count(),
        )
        call_command("seed_demo", stdout=StringIO())
        self.assertEqual(snapshot, (
            User.objects.count(), BorrowRequest.objects.count(),
            BorrowRecord.objects.count(), Fine.objects.count(),
        ))
        for book in Book.objects.all():
            active = book.borrow_records.filter(status="ISSUED", return_date__isnull=True).count()
            self.assertEqual(book.available_copies, book.total_copies - active)
        self.assertEqual(BorrowRequest.objects.filter(status="PENDING").count(), 3)
        self.assertEqual(BorrowRecord.objects.filter(status="ISSUED").count(), 3)
        self.assertEqual(BorrowRecord.objects.filter(status="RETURNED").count(), 3)
        for fine in Fine.objects.all():
            self.assertEqual(fine.amount, BorrowRecord.calculate_borrowing_fee(fine.duration_days))

    def test_no_default_password_and_existing_passwords_untouched(self):
        initial_secret = secrets.token_urlsafe(12)
        next_secret = secrets.token_urlsafe(12)
        call_command("seed_demo", password=initial_secret, stdout=StringIO())
        user = User.objects.get(username="demo_member1")
        self.assertTrue(user.check_password(initial_secret))
        call_command("seed_demo", password=next_secret, stdout=StringIO())
        user.refresh_from_db()
        self.assertTrue(user.check_password(initial_secret))

    def test_requires_catalogue(self):
        Book.objects.all().delete()
        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())
