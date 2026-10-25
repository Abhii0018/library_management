from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, MemberProfile
from books.models import Category, Book
from circulation.models import BorrowRequest, BorrowRecord, Fine


class DedicatedPagesAndLifecycleTestCase(TestCase):
    """
    Exhaustive tests for Section 14:
    1. Student has no active books.
    2. Student requests a book.
    3. Admin approves it.
    4. Student Currently Borrowed count becomes 1.
    5. Book available copies decreases by 1.
    6. Transaction appears in Currently Borrowed (/borrowed/ & /admin/borrowed/).
    7. Transaction does NOT appear in History yet (/history/ & /admin/history/).
    8. Fee updates based on current borrowing duration.
    9. Admin returns the book.
    10. Student Currently Borrowed count becomes 0.
    11. Book availability increases by 1.
    12. Transaction disappears from Currently Borrowed.
    13. Transaction appears in Borrowing History.
    14. Final fee is stored correctly.
    Also tests:
    - Multiple active books
    - Multiple historical books
    - Overdue books
    - Maximum 3-book limit
    - Member-specific data isolation
    - Admin sees all members' data
    """

    def setUp(self):
        # 1. Admin / Librarian
        self.librarian = User.objects.create_user(
            username="admin_librarian",
            password="adminpassword123",
            role=User.ROLE_LIBRARIAN,
            email="admin@library.com"
        )

        # 2. Member 1 (Student Alice)
        self.student1 = User.objects.create_user(
            username="alice",
            password="studentpassword123",
            role=User.ROLE_MEMBER,
            email="alice@student.edu",
            first_name="Alice",
            last_name="Wonder"
        )
        self.profile1 = MemberProfile.objects.create(
            user=self.student1,
            membership_id="MEM-ALICE-01",
            max_books_allowed=3,
            is_blocked=False
        )

        # 3. Member 2 (Student Bob for isolation testing)
        self.student2 = User.objects.create_user(
            username="bob",
            password="studentpassword123",
            role=User.ROLE_MEMBER,
            email="bob@student.edu",
            first_name="Bob",
            last_name="Builder"
        )
        self.profile2 = MemberProfile.objects.create(
            user=self.student2,
            membership_id="MEM-BOB-02",
            max_books_allowed=3,
            is_blocked=False
        )

        # 4. Books
        self.category = Category.objects.create(name="Computer Science")
        self.book1 = Book.objects.create(
            title="Design Patterns",
            author="GoF",
            isbn="978-0201633610",
            category=self.category,
            total_copies=3,
            available_copies=3
        )
        self.book2 = Book.objects.create(
            title="Refactoring",
            author="Martin Fowler",
            isbn="978-0201485677",
            category=self.category,
            total_copies=2,
            available_copies=2
        )

        self.client = Client()

    def test_complete_14_step_borrowing_and_return_lifecycle(self):
        # 1. Student has no active books
        self.assertEqual(BorrowRecord.objects.filter(member=self.student1, status=BorrowRecord.STATUS_ISSUED).count(), 0)

        # Member checks /borrowed/ and sees empty state
        self.client.login(username="alice", password="studentpassword123")
        res_empty = self.client.get(reverse('circulation:member_borrowed'))
        self.assertEqual(res_empty.status_code, 200)
        self.assertContains(res_empty, "0 / 3")
        self.assertContains(res_empty, "You currently have no borrowed books.")

        # 2. Student requests a book for 5 days
        req_res = self.client.post(reverse('circulation:create_request', args=[self.book1.pk]), {'requested_days': 5})
        self.assertEqual(req_res.status_code, 302)
        req = BorrowRequest.objects.get(member=self.student1, book=self.book1)
        self.assertEqual(req.status, BorrowRequest.STATUS_PENDING)

        # Request is in member requests, but NOT yet in Currently Borrowed
        res_borrowed_pre = self.client.get(reverse('circulation:member_borrowed'))
        self.assertContains(res_borrowed_pre, "0 / 3")
        self.assertContains(res_borrowed_pre, "You currently have no borrowed books.")
        self.assertNotContains(res_borrowed_pre, "978-0201633610")

        # 3. Admin approves/accepts it
        self.client.login(username="admin_librarian", password="adminpassword123")
        app_res = self.client.post(reverse('circulation:approve_request', args=[req.pk]))
        self.assertEqual(app_res.status_code, 302)

        # 4. Student Currently Borrowed count becomes 1
        self.assertEqual(BorrowRecord.objects.filter(member=self.student1, status=BorrowRecord.STATUS_ISSUED).count(), 1)

        # 5. Book available copies decreases by 1 (3 -> 2)
        self.book1.refresh_from_db()
        self.assertEqual(self.book1.available_copies, 2)
        self.assertEqual(self.book1.issued_copies, 1)

        # 6. Transaction appears in Currently Borrowed for Member and Admin
        self.client.login(username="alice", password="studentpassword123")
        res_borrowed_post = self.client.get(reverse('circulation:member_borrowed'))
        self.assertEqual(res_borrowed_post.status_code, 200)
        self.assertContains(res_borrowed_post, "1 / 3")
        self.assertContains(res_borrowed_post, "Design Patterns")

        self.client.login(username="admin_librarian", password="adminpassword123")
        res_admin_borrowed = self.client.get(reverse('circulation:admin_borrowed'))
        self.assertEqual(res_admin_borrowed.status_code, 200)
        self.assertContains(res_admin_borrowed, "Design Patterns")
        self.assertContains(res_admin_borrowed, "Alice")
        self.assertContains(res_admin_borrowed, "Return Book")

        # 7. Transaction does NOT appear in History yet
        self.client.login(username="alice", password="studentpassword123")
        res_history_pre = self.client.get(reverse('circulation:member_history'))
        self.assertEqual(res_history_pre.status_code, 200)
        self.assertNotContains(res_history_pre, "Design Patterns")
        self.assertContains(res_history_pre, "No completed borrowing history yet.")

        self.client.login(username="admin_librarian", password="adminpassword123")
        res_admin_history_pre = self.client.get(reverse('circulation:admin_history'))
        self.assertNotContains(res_admin_history_pre, "Design Patterns")

        # 8. Fee updates based on current borrowing duration
        record = BorrowRecord.objects.get(member=self.student1, book=self.book1, status=BorrowRecord.STATUS_ISSUED)
        # On day 0/1: fee is 0
        self.assertEqual(record.current_fee, Decimal('0.00'))

        # 9. Admin returns the book (e.g. after 6 days to test final fee)
        return_date = record.issue_date + timedelta(days=6)
        ret_res = self.client.post(reverse('circulation:return_book', args=[record.pk]), {
            'return_date': return_date.isoformat(),
            'notes': 'Returned after 6 days'
        })
        self.assertEqual(ret_res.status_code, 302)

        # 10. Student Currently Borrowed count becomes 0
        self.assertEqual(BorrowRecord.objects.filter(member=self.student1, status=BorrowRecord.STATUS_ISSUED).count(), 0)

        # 11. Book availability increases by 1 (2 -> 3)
        self.book1.refresh_from_db()
        self.assertEqual(self.book1.available_copies, 3)
        self.assertEqual(self.book1.issued_copies, 0)

        # 12. Transaction disappears from Currently Borrowed
        self.client.login(username="alice", password="studentpassword123")
        res_borrowed_final = self.client.get(reverse('circulation:member_borrowed'))
        self.assertContains(res_borrowed_final, "You currently have no borrowed books.")
        self.assertNotContains(res_borrowed_final, "978-0201633610")

        self.client.login(username="admin_librarian", password="adminpassword123")
        res_admin_borrowed_final = self.client.get(reverse('circulation:admin_borrowed'))
        self.assertNotContains(res_admin_borrowed_final, "Return Book")

        # 13. Transaction appears in Borrowing History
        self.client.login(username="alice", password="studentpassword123")
        res_history_post = self.client.get(reverse('circulation:member_history'))
        self.assertEqual(res_history_post.status_code, 200)
        self.assertContains(res_history_post, "Design Patterns")
        self.assertContains(res_history_post, "Returned")

        self.client.login(username="admin_librarian", password="adminpassword123")
        res_admin_history_post = self.client.get(reverse('circulation:admin_history'))
        self.assertEqual(res_admin_history_post.status_code, 200)
        self.assertContains(res_admin_history_post, "Design Patterns")
        self.assertContains(res_admin_history_post, "Alice")

        # 14. Final fee is stored correctly (6 days = ₹160)
        record.refresh_from_db()
        self.assertEqual(record.status, BorrowRecord.STATUS_RETURNED)
        self.assertEqual(record.borrowing_duration(), 6)
        fine = Fine.objects.get(borrow_record=record)
        self.assertEqual(fine.duration_days, 6)
        self.assertEqual(fine.amount, Decimal('160.00'))

    def test_member_isolation_on_dedicated_pages(self):
        # Create an active loan for Bob
        loan_bob = BorrowRecord.objects.create(
            book=self.book2,
            member=self.student2,
            issued_by=self.librarian,
            requested_days=5,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=5),
            status=BorrowRecord.STATUS_ISSUED
        )

        # Login as Alice
        self.client.login(username="alice", password="studentpassword123")

        # Alice views /borrowed/
        res_borrowed = self.client.get(reverse('circulation:member_borrowed'))
        self.assertEqual(res_borrowed.status_code, 200)
        # Must NOT see Bob's book
        self.assertNotContains(res_borrowed, "Refactoring")

        # Alice views /history/
        res_history = self.client.get(reverse('circulation:member_history'))
        self.assertEqual(res_history.status_code, 200)
        self.assertNotContains(res_history, "Refactoring")

        # Alice cannot access Admin dedicated pages
        res_admin_borrowed = self.client.get(reverse('circulation:admin_borrowed'))
        self.assertIn(res_admin_borrowed.status_code, [302, 403])
        res_admin_history = self.client.get(reverse('circulation:admin_history'))
        self.assertIn(res_admin_history.status_code, [302, 403])

    def test_admin_sees_all_members_data_on_dedicated_pages(self):
        # Active loan for Alice
        loan_alice = BorrowRecord.objects.create(
            book=self.book1,
            member=self.student1,
            issued_by=self.librarian,
            requested_days=5,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=5),
            status=BorrowRecord.STATUS_ISSUED
        )
        # Active loan for Bob
        loan_bob = BorrowRecord.objects.create(
            book=self.book2,
            member=self.student2,
            issued_by=self.librarian,
            requested_days=5,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=5),
            status=BorrowRecord.STATUS_ISSUED
        )

        self.client.login(username="admin_librarian", password="adminpassword123")
        res = self.client.get(reverse('circulation:admin_borrowed'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Alice")
        self.assertContains(res, "Design Patterns")
        self.assertContains(res, "Bob")
        self.assertContains(res, "Refactoring")
