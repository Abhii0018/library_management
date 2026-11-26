import csv
import io
from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from circulation.models import BookReservation, BorrowRecord, Fine
from circulation.tests_showcase import FAST_HASHER, make_book, make_member, make_staff


def read_csv(response) -> list[list[str]]:
    body = b"".join(response.streaming_content).decode("utf-8-sig")
    return list(csv.reader(io.StringIO(body)))


def make_loan(book, member, staff, issued_days_ago=1, term_days=14, returned_days_ago=None):
    today = timezone.now().date()
    loan = BorrowRecord.objects.create(
        book=book, member=member, issued_by=staff,
        issue_date=today - timedelta(days=issued_days_ago),
        due_date=today - timedelta(days=issued_days_ago) + timedelta(days=term_days),
        requested_days=term_days,
    )
    if returned_days_ago is not None:
        loan.return_date = today - timedelta(days=returned_days_ago)
        loan.status = BorrowRecord.STATUS_RETURNED
        loan.save()
    else:
        Book = type(book)
        Book.objects.filter(pk=book.pk).update(available_copies=book.available_copies - 1)
        book.refresh_from_db()
    return loan


@FAST_HASHER
class CirculationCsvExportTests(TestCase):
    def setUp(self):
        self.staff = make_staff()
        self.member = make_member("alice")
        self.url = reverse("circulation:export_csv")

    def test_requires_librarian(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertNotEqual(response.get("Content-Type", "").split(";")[0], "text/csv")
        self.assertIn(response.status_code, (302, 403))

    def test_streams_attachment_with_expected_columns_and_values(self):
        book = make_book("9780000000001", "Algorithms", copies=3)
        active = make_loan(book, self.member, self.staff, issued_days_ago=2)
        overdue = make_loan(book, self.member, self.staff, issued_days_ago=30, term_days=7)
        returned = make_loan(book, self.member, self.staff, issued_days_ago=10, returned_days_ago=4)
        Fine.objects.create(
            borrow_record=returned, member=self.member, duration_days=6,
            overdue_days=0, amount=Decimal("160.00"), is_paid=True,
        )

        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertTrue(response.streaming)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        today = timezone.now().date().isoformat()
        self.assertEqual(
            response["Content-Disposition"],
            f'attachment; filename="LibriCore_Circulation_Audit_{today}.csv"',
        )

        rows = read_csv(response)
        self.assertEqual(rows[0], [
            "Transaction ID", "Book Title", "ISBN", "Member ID", "Student Name",
            "Issue Date", "Due Date", "Return Date", "Status", "Fee Amount",
        ])
        by_id = {int(r[0]): r for r in rows[1:]}
        self.assertEqual(len(by_id), 3)
        self.assertEqual(by_id[active.pk][8], "Issued")
        self.assertEqual(by_id[overdue.pk][8], "Overdue")
        self.assertEqual(by_id[returned.pk][8], "Returned")
        self.assertEqual(by_id[returned.pk][9], "160.00")
        self.assertEqual(by_id[returned.pk][7], returned.return_date.isoformat())
        self.assertEqual(by_id[active.pk][7], "")
        self.assertEqual(by_id[active.pk][1:5], ["Algorithms", "9780000000001", "MEM-alice", "alice"])
        self.assertEqual(by_id[active.pk][9], f"{active.current_fee:.2f}")

    def test_formula_injection_is_neutralised(self):
        book = make_book("9780000000002", "=HYPERLINK(\"http://evil\")", copies=2)
        make_loan(book, self.member, self.staff)
        self.client.force_login(self.staff)
        rows = read_csv(self.client.get(self.url))
        self.assertTrue(rows[1][1].startswith("'="))

    def test_query_count_does_not_grow_with_rows(self):
        self.client.force_login(self.staff)

        def count_queries() -> int:
            with CaptureQueriesContext(connection) as ctx:
                read_csv(self.client.get(self.url))
            return len(ctx)

        book = make_book("9780000000003", "Networks", copies=30)
        for _ in range(2):
            make_loan(book, self.member, self.staff)
        small = count_queries()
        for _ in range(10):
            make_loan(book, self.member, self.staff)
        self.assertEqual(count_queries(), small)

    def test_export_buttons_rendered(self):
        self.client.force_login(self.staff)
        for name in ("dashboard:staff_dashboard", "circulation:admin_borrowed"):
            response = self.client.get(reverse(name))
            self.assertContains(response, "Export Audit CSV")
            self.assertContains(response, self.url)


@FAST_HASHER
class LoanRenewalTests(TestCase):
    def setUp(self):
        self.staff = make_staff()
        self.member = make_member("alice")
        self.book = make_book("9780000000010", "Databases", copies=2)
        self.loan = make_loan(self.book, self.member, self.staff, issued_days_ago=3, term_days=7)
        self.url = reverse("circulation:renew_loan", args=[self.loan.pk])

    def test_successful_renewal(self):
        original_due = self.loan.due_date
        self.client.force_login(self.member)
        response = self.client.post(self.url, follow=True)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.due_date, original_due + timedelta(days=7))
        self.assertTrue(self.loan.is_extended)
        self.assertIn("Renewed by member", self.loan.notes)
        self.assertContains(response, "renewed")
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)

    def test_second_renewal_rejected(self):
        self.client.force_login(self.member)
        self.client.post(self.url)
        due_after_first = BorrowRecord.objects.get(pk=self.loan.pk).due_date
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, "already been extended")
        self.assertEqual(BorrowRecord.objects.get(pk=self.loan.pk).due_date, due_after_first)

    def test_overdue_loan_rejected(self):
        BorrowRecord.objects.filter(pk=self.loan.pk).update(
            due_date=timezone.now().date() - timedelta(days=1)
        )
        self.client.force_login(self.member)
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, "Overdue loans cannot be renewed")
        self.assertFalse(BorrowRecord.objects.get(pk=self.loan.pk).is_extended)

    def test_loan_due_today_can_be_renewed(self):
        BorrowRecord.objects.filter(pk=self.loan.pk).update(due_date=timezone.now().date())
        self.client.force_login(self.member)
        self.client.post(self.url)
        self.assertTrue(BorrowRecord.objects.get(pk=self.loan.pk).is_extended)

    def test_returned_loan_rejected(self):
        BorrowRecord.objects.filter(pk=self.loan.pk).update(
            status=BorrowRecord.STATUS_RETURNED, return_date=timezone.now().date()
        )
        self.client.force_login(self.member)
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, "no longer active")
        self.assertFalse(BorrowRecord.objects.get(pk=self.loan.pk).is_extended)

    def test_other_member_and_staff_cannot_renew(self):
        intruder = make_member("mallory")
        for user in (intruder, self.staff):
            self.client.force_login(user)
            self.assertEqual(self.client.post(self.url).status_code, 404)
        self.assertFalse(BorrowRecord.objects.get(pk=self.loan.pk).is_extended)

    def test_get_not_allowed_and_anonymous_redirected(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.logout()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_open_redirect_ignored(self):
        self.client.force_login(self.member)
        response = self.client.post(self.url, {"next": "https://evil.example/"})
        self.assertEqual(response["Location"], reverse("circulation:member_borrowed"))

    def test_buttons_only_for_eligible_loans(self):
        self.client.force_login(self.member)
        for name in ("dashboard:member_dashboard", "circulation:member_borrowed"):
            self.assertContains(self.client.get(reverse(name)), "Extend Loan (+7 Days)")
        self.client.post(self.url)
        for name in ("dashboard:member_dashboard", "circulation:member_borrowed"):
            self.assertNotContains(self.client.get(reverse(name)), "Extend Loan (+7 Days)")

    def test_can_renew_property(self):
        self.assertTrue(self.loan.can_renew)
        self.loan.is_extended = True
        self.assertFalse(self.loan.can_renew)


@FAST_HASHER
class ReservationTests(TestCase):
    def setUp(self):
        self.staff = make_staff()
        self.staff.email = "desk@example.com"
        self.staff.save()
        self.alice = make_member("alice")
        self.bob = make_member("bob")
        self.book = make_book("9780000000020", "Compilers", copies=1)
        holder = make_member("holder")
        self.loan = make_loan(self.book, holder, self.staff, issued_days_ago=2)
        self.detail = reverse("books:book_detail", args=[self.book.pk])

    def reserve(self, user, action="reserve"):
        self.client.force_login(user)
        return self.client.post(self.detail, {"action": action}, follow=True)

    def test_member_can_reserve_unavailable_book(self):
        response = self.reserve(self.alice)
        self.assertContains(response, "Hold placed")
        self.assertEqual(BookReservation.objects.filter(member=self.alice, status="PENDING").count(), 1)
        self.assertContains(response, "On the Waitlist")

    def test_duplicate_pending_reservation_blocked(self):
        self.reserve(self.alice)
        response = self.reserve(self.alice)
        self.assertContains(response, "already on the waitlist")
        self.assertEqual(BookReservation.objects.count(), 1)

    def test_database_constraint_blocks_duplicate_pending(self):
        BookReservation.objects.create(book=self.book, member=self.alice)
        with self.assertRaises(IntegrityError), transaction.atomic():
            BookReservation.objects.create(book=self.book, member=self.alice)

    def test_constraint_allows_new_pending_after_cancel_or_fulfilment(self):
        first = BookReservation.objects.create(book=self.book, member=self.alice)
        first.status = BookReservation.STATUS_CANCELLED
        first.save()
        BookReservation.objects.create(book=self.book, member=self.alice)
        self.assertEqual(BookReservation.objects.filter(member=self.alice).count(), 2)

    def test_get_does_not_create_reservation(self):
        self.client.force_login(self.alice)
        self.client.get(self.detail, {"action": "reserve"})
        self.assertEqual(BookReservation.objects.count(), 0)

    def test_cannot_reserve_when_copies_available(self):
        other = make_book("9780000000021", "Graphics", copies=2)
        self.client.force_login(self.alice)
        response = self.client.post(reverse("books:book_detail", args=[other.pk]), {"action": "reserve"}, follow=True)
        self.assertContains(response, "Copies are on the shelf")
        self.assertEqual(BookReservation.objects.count(), 0)

    def test_staff_blocked_member_and_current_borrower_cannot_reserve(self):
        self.reserve(self.staff)
        self.alice.member_profile.is_blocked = True
        self.alice.member_profile.save()
        self.reserve(self.alice)
        self.reserve(self.loan.member)
        self.assertEqual(BookReservation.objects.count(), 0)

    def test_cancel_hold(self):
        self.reserve(self.alice)
        response = self.reserve(self.alice, action="cancel")
        self.assertContains(response, "was cancelled")
        self.assertEqual(BookReservation.objects.get().status, BookReservation.STATUS_CANCELLED)

    def test_cannot_cancel_someone_elses_hold(self):
        self.reserve(self.alice)
        self.reserve(self.bob, action="cancel")
        self.assertEqual(BookReservation.objects.get().status, BookReservation.STATUS_PENDING)

    def test_queue_position_shown(self):
        self.reserve(self.alice)
        response = self.reserve(self.bob)
        self.assertEqual(response.context["queue_position"], 2)
        self.assertEqual(response.context["waitlist_count"], 2)

    def return_loan(self):
        self.client.force_login(self.staff)
        return self.client.post(
            reverse("circulation:return_book", args=[self.loan.pk]),
            {"return_date": timezone.now().date()}, follow=True,
        )

    def test_return_fulfils_oldest_pending_and_notifies_staff(self):
        BookReservation.objects.create(book=self.book, member=self.alice)
        BookReservation.objects.create(book=self.book, member=self.bob)
        response = self.return_loan()
        statuses = {r.member.username: r.status for r in BookReservation.objects.select_related("member")}
        self.assertEqual(statuses, {"alice": "FULFILLED", "bob": "PENDING"})
        self.assertContains(response, "Hold fulfilled")
        self.assertContains(response, "MEM-alice")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["desk@example.com"])
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)

    def test_return_skips_blocked_member(self):
        BookReservation.objects.create(book=self.book, member=self.alice)
        BookReservation.objects.create(book=self.book, member=self.bob)
        self.alice.member_profile.is_blocked = True
        self.alice.member_profile.save()
        self.return_loan()
        statuses = {r.member.username: r.status for r in BookReservation.objects.select_related("member")}
        self.assertEqual(statuses, {"alice": "PENDING", "bob": "FULFILLED"})

    def test_return_ignores_cancelled_holds(self):
        BookReservation.objects.create(book=self.book, member=self.alice, status="CANCELLED")
        response = self.return_loan()
        self.assertNotContains(response, "Hold fulfilled")
        self.assertEqual(len(mail.outbox), 0)

    def test_return_without_reservations_still_works(self):
        response = self.return_loan()
        self.assertEqual(response.status_code, 200)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.status, BorrowRecord.STATUS_RETURNED)

    def test_hold_on_other_book_untouched(self):
        other = make_book("9780000000022", "Security", copies=1)
        BookReservation.objects.create(book=other, member=self.alice)
        self.return_loan()
        self.assertEqual(BookReservation.objects.get().status, BookReservation.STATUS_PENDING)
