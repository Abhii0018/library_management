from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, MemberProfile
from books.models import Category, Book
from circulation.models import BorrowRequest, BorrowRecord, Fine


class CompleteLibraryWorkflowTestCase(TestCase):
    """
    Exhaustive functional and permission tests satisfying Section 26 of requirements:
    - Member workflows (1-11)
    - Admin workflows (12-29)
    - Exact Borrowing Fee Policy tests (1d, 2d, 3d, 4d, 5d, 6d, 7d)
    - Boundary validations and constraints
    - Backend security and permission isolation
    """

    def setUp(self):
        # 1. Admin / Librarian User
        self.librarian = User.objects.create_user(
            username="head_librarian",
            password="adminpassword123",
            role=User.ROLE_LIBRARIAN,
            email="librarian@library.org",
            first_name="Admin",
            last_name="Officer"
        )

        # 2. Member User 1 (Active Student)
        self.student1 = User.objects.create_user(
            username="student_alice",
            password="studentpassword123",
            role=User.ROLE_MEMBER,
            email="alice@university.edu",
            first_name="Alice",
            last_name="Johnson"
        )
        self.profile1 = MemberProfile.objects.create(
            user=self.student1,
            membership_id="LIB-STU-001",
            max_books_allowed=3,
            is_blocked=False
        )

        # 3. Member User 2 (Active Student for cross-user tests)
        self.student2 = User.objects.create_user(
            username="student_bob",
            password="studentpassword123",
            role=User.ROLE_MEMBER,
            email="bob@university.edu",
            first_name="Bob",
            last_name="Smith"
        )
        self.profile2 = MemberProfile.objects.create(
            user=self.student2,
            membership_id="LIB-STU-002",
            max_books_allowed=3,
            is_blocked=False
        )

        # 4. Member User 3 (Blocked Student)
        self.blocked_student = User.objects.create_user(
            username="student_blocked",
            password="blockedpassword123",
            role=User.ROLE_MEMBER,
            email="blocked@university.edu"
        )
        self.blocked_profile = MemberProfile.objects.create(
            user=self.blocked_student,
            membership_id="LIB-STU-003",
            max_books_allowed=3,
            is_blocked=True
        )

        # 5. Catalog Books
        self.category = Category.objects.create(name="Astrophysics", description="Cosmology & Space")
        self.book1 = Book.objects.create(
            title="A Brief History of Time",
            author="Stephen Hawking",
            isbn="978-0553380163",
            category=self.category,
            book_value=Decimal('599.00'),
            total_copies=5,
            available_copies=5,
            shelf_location="A-101",
            description="From the Big Bang to Black Holes"
        )
        self.book_scarce = Book.objects.create(
            title="Rare Manuscript",
            author="Archimedes",
            isbn="978-0000000001",
            category=self.category,
            book_value=Decimal('1500.00'),
            total_copies=1,
            available_copies=1,
            shelf_location="R-Vault"
        )

        self.client = Client()

    # ==========================================
    # 1. MEMBER WORKFLOW TESTS (Section 26: 1-11)
    # ==========================================

    def test_01_member_login(self):
        login = self.client.login(username="student_alice", password="studentpassword123")
        self.assertTrue(login)

    def test_02_03_member_browse_search_filter_books(self):
        self.client.login(username="student_alice", password="studentpassword123")
        # Browse
        res = self.client.get(reverse('books:book_list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "A Brief History of Time")

        # Search query
        res_search = self.client.get(reverse('books:book_list') + '?q=Hawking')
        self.assertEqual(res_search.status_code, 200)
        self.assertContains(res_search, "A Brief History of Time")

        # Filter category
        res_filter = self.client.get(reverse('books:book_list') + f'?category={self.category.pk}')
        self.assertEqual(res_filter.status_code, 200)
        self.assertContains(res_filter, "A Brief History of Time")

    def test_04_05_member_views_book_details_and_book_value(self):
        self.client.login(username="student_alice", password="studentpassword123")
        res = self.client.get(reverse('books:book_detail', args=[self.book1.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "A Brief History of Time")
        self.assertContains(res, "Stephen Hawking")
        self.assertContains(res, "978-0553380163")
        # Clearly labeled Book Value
        self.assertContains(res, "Book Value:")
        self.assertContains(res, "599.00")
        # Request to borrow form present
        self.assertContains(res, "Request to Borrow")

    def test_06_to_10_member_submits_borrow_request_pending_status(self):
        self.client.login(username="student_alice", password="studentpassword123")

        # Submit request for 5 days
        response = self.client.post(reverse('circulation:create_request', args=[self.book1.pk]), {
            'requested_days': 5,
            'notes': 'Preparation for astronomy seminar'
        })
        self.assertEqual(response.status_code, 302)

        # Verify BorrowRequest created with PENDING status
        req = BorrowRequest.objects.get(member=self.student1, book=self.book1)
        self.assertEqual(req.status, BorrowRequest.STATUS_PENDING)
        self.assertEqual(req.requested_days, 5)

        # IMPORTANT RULE: Creating a request does NOT decrease available copies
        self.book1.refresh_from_db()
        self.assertEqual(self.book1.available_copies, 5)

        # Verify member sees request status on Book Details page
        detail_res = self.client.get(reverse('books:book_detail', args=[self.book1.pk]))
        self.assertEqual(detail_res.status_code, 200)
        self.assertContains(detail_res, "Request Pending")
        self.assertContains(detail_res, "5 days")

        # Verify member sees request on their Dashboard
        dash_res = self.client.get(reverse('dashboard:member_dashboard'))
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, "A Brief History of Time")
        self.assertContains(dash_res, "5 days")
        self.assertContains(dash_res, "Request Pending")

    def test_11_member_cannot_access_admin_pages(self):
        self.client.login(username="student_alice", password="studentpassword123")
        forbidden_urls = [
            reverse('dashboard:librarian_dashboard'),
            reverse('books:book_create'),
            reverse('books:book_edit', args=[self.book1.pk]),
            reverse('books:book_delete', args=[self.book1.pk]),
            reverse('accounts:member_list'),
            reverse('accounts:member_create'),
            reverse('accounts:member_detail', args=[self.student2.pk]),
            reverse('circulation:request_list'),
            reverse('circulation:issue_book'),
            reverse('circulation:transaction_list'),
            reverse('circulation:fine_list'),
        ]
        for url in forbidden_urls:
            resp = self.client.get(url)
            self.assertIn(resp.status_code, [302, 403], f"Member could access {url} with code {resp.status_code}")

    # ==========================================
    # 2. ADMIN WORKFLOW TESTS (Section 26: 12-29)
    # ==========================================

    def test_12_to_16_admin_views_dashboard_books_members_requests(self):
        self.client.login(username="head_librarian", password="adminpassword123")

        # Admin Dashboard
        dash_res = self.client.get(reverse('dashboard:librarian_dashboard'))
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, "Total Titles")
        self.assertContains(dash_res, "Available Copies")
        self.assertContains(dash_res, "Total Members")

        # Admin views all books
        books_res = self.client.get(reverse('books:book_list'))
        self.assertEqual(books_res.status_code, 200)

        # Admin views all members
        members_res = self.client.get(reverse('accounts:member_list'))
        self.assertEqual(members_res.status_code, 200)
        self.assertContains(members_res, "student_alice")
        self.assertContains(members_res, "student_bob")

        # Admin views all requests
        req_res = self.client.get(reverse('circulation:request_list'))
        self.assertEqual(req_res.status_code, 200)

    def test_17_admin_accepts_request_immediately_issues_book(self):
        # Alice requests 5 days
        req = BorrowRequest.objects.create(
            member=self.student1,
            book=self.book1,
            requested_days=5,
            status=BorrowRequest.STATUS_PENDING
        )

        initial_available = self.book1.available_copies # 5
        self.client.login(username="head_librarian", password="adminpassword123")
        app_res = self.client.post(reverse('circulation:approve_request', args=[req.pk]))
        self.assertEqual(app_res.status_code, 302)

        # 1. BorrowRequest status updated
        req.refresh_from_db()
        self.assertEqual(req.status, BorrowRequest.STATUS_APPROVED)
        self.assertEqual(req.reviewed_by, self.librarian)
        self.assertIsNotNone(req.reviewed_at)

        # 2. Available copies decrease by EXACTLY 1 immediately
        self.book1.refresh_from_db()
        self.assertEqual(self.book1.available_copies, initial_available - 1)
        self.assertEqual(self.book1.issued_copies, 1)

        # 3. Transaction record created immediately
        record = BorrowRecord.objects.get(member=self.student1, book=self.book1, status=BorrowRecord.STATUS_ISSUED)
        today = timezone.now().date()
        self.assertEqual(record.issue_date, today)
        self.assertEqual(record.requested_days, 5)
        self.assertEqual(record.due_date, today + timedelta(days=5))
        self.assertEqual(record.issued_by, self.librarian)
        self.assertEqual(record.borrow_request, req)

        # 4. Student sees book immediately on their dashboard as Active Loan
        self.client.login(username="student_alice", password="studentpassword123")
        dash_res = self.client.get(reverse('dashboard:member_dashboard'))
        self.assertContains(dash_res, "A Brief History of Time")
        self.assertContains(dash_res, "Active Loan")
        self.assertContains(dash_res, "Approved & Borrowed")

    def test_18_admin_rejects_request(self):
        req = BorrowRequest.objects.create(
            member=self.student1,
            book=self.book1,
            requested_days=7,
            status=BorrowRequest.STATUS_PENDING
        )

        initial_available = self.book1.available_copies
        self.client.login(username="head_librarian", password="adminpassword123")
        rej_res = self.client.post(reverse('circulation:reject_request', args=[req.pk]))
        self.assertEqual(rej_res.status_code, 302)

        req.refresh_from_db()
        self.assertEqual(req.status, BorrowRequest.STATUS_REJECTED)
        self.assertEqual(req.reviewed_by, self.librarian)

        # Copies unaffected, no transaction created
        self.book1.refresh_from_db()
        self.assertEqual(self.book1.available_copies, initial_available)
        self.assertFalse(BorrowRecord.objects.filter(member=self.student1, book=self.book1).exists())

        # Student sees "Request Rejected"
        self.client.login(username="student_alice", password="studentpassword123")
        dash_res = self.client.get(reverse('dashboard:member_dashboard'))
        self.assertContains(dash_res, "Request Rejected")

    def test_19_admin_cannot_accept_request_if_book_out_of_stock(self):
        # Scarce book has 1 copy
        self.book_scarce.available_copies = 0
        self.book_scarce.save()

        req = BorrowRequest.objects.create(
            member=self.student1,
            book=self.book_scarce,
            requested_days=3,
            status=BorrowRequest.STATUS_PENDING
        )

        self.client.login(username="head_librarian", password="adminpassword123")
        res = self.client.post(reverse('circulation:approve_request', args=[req.pk]), follow=True)
        self.assertContains(res, "Book is no longer available.")

        req.refresh_from_db()
        self.assertEqual(req.status, BorrowRequest.STATUS_PENDING)
        self.assertFalse(BorrowRecord.objects.filter(book=self.book_scarce).exists())

    def test_23_to_26_return_book_duration_and_fee(self):
        # Issue on Oct 10, Return on Oct 16 (Duration = 6 days)
        issue_date = date(2026, 10, 10)
        due_date = date(2026, 10, 15)
        return_date = date(2026, 10, 16)

        self.book1.available_copies = 4
        self.book1.save()

        loan = BorrowRecord.objects.create(
            book=self.book1,
            member=self.student1,
            issued_by=self.librarian,
            requested_days=5,
            issue_date=issue_date,
            due_date=due_date,
            status=BorrowRecord.STATUS_ISSUED
        )

        self.client.login(username="head_librarian", password="adminpassword123")
        ret_res = self.client.post(reverse('circulation:return_book', args=[loan.pk]), {
            'return_date': return_date.isoformat(),
            'notes': 'Book returned'
        })
        self.assertEqual(ret_res.status_code, 302)

        # 24. Available copies increase by 1
        self.book1.refresh_from_db()
        self.assertEqual(self.book1.available_copies, 5)

        loan.refresh_from_db()
        self.assertEqual(loan.status, BorrowRecord.STATUS_RETURNED)
        self.assertEqual(loan.return_date, return_date)

        # 25. Actual borrowing duration (Oct 16 - Oct 10 = 6 days)
        self.assertEqual(loan.borrowing_duration(), 6)

        # 26. Fee calculation: 6 days => (6-2)*20 + 100 = ₹160
        fine = Fine.objects.get(borrow_record=loan)
        self.assertEqual(fine.duration_days, 6)
        self.assertEqual(fine.amount, Decimal('160.00'))
        self.assertFalse(fine.is_paid)

        # Cannot return again
        repeat_res = self.client.post(reverse('circulation:return_book', args=[loan.pk]), {
            'return_date': return_date.isoformat(),
        })
        self.assertEqual(repeat_res.status_code, 302)

    def test_27_to_29_admin_views_transactions_fees_and_member_details(self):
        self.client.login(username="head_librarian", password="adminpassword123")

        # 27. View all transactions
        tx_res = self.client.get(reverse('circulation:transaction_list'))
        self.assertEqual(tx_res.status_code, 200)

        # 28. View all fees
        fee_res = self.client.get(reverse('circulation:fine_list'))
        self.assertEqual(fee_res.status_code, 200)

        # 29. View member details (shows borrow requests, loans, fees)
        mem_res = self.client.get(reverse('accounts:member_detail', args=[self.student1.pk]))
        self.assertEqual(mem_res.status_code, 200)
        self.assertContains(mem_res, "Alice Johnson")
        self.assertContains(mem_res, "LIB-STU-001")
        self.assertContains(mem_res, "Borrow Requests")

    # ==========================================
    # 3. BORROWING FEE POLICY TESTS (Section 16 & 26)
    # ==========================================

    def test_fee_policy_all_cases(self):
        """
        Policy specification:
        First 2 days: FREE
        Day 3 onward: ₹20 per day
        If borrowing duration exceeds 5 days: Add one-time ₹100 penalty
        - 1 day  -> ₹0
        - 2 days -> ₹0
        - 3 days -> ₹20   ((3-2)*20)
        - 4 days -> ₹40   ((4-2)*20)
        - 5 days -> ₹60   ((5-2)*20)
        - 6 days -> ₹160  ((6-2)*20 + 100)
        - 7 days -> ₹180  ((7-2)*20 + 100)
        """
        self.assertEqual(BorrowRecord.calculate_borrowing_fee(1), Decimal('0.00'))
        self.assertEqual(BorrowRecord.calculate_borrowing_fee(2), Decimal('0.00'))
        self.assertEqual(BorrowRecord.calculate_borrowing_fee(3), Decimal('20.00'))
        self.assertEqual(BorrowRecord.calculate_borrowing_fee(4), Decimal('40.00'))
        self.assertEqual(BorrowRecord.calculate_borrowing_fee(5), Decimal('60.00'))
        self.assertEqual(BorrowRecord.calculate_borrowing_fee(6), Decimal('160.00'))
        self.assertEqual(BorrowRecord.calculate_borrowing_fee(7), Decimal('180.00'))

    # ==========================================
    # 4. VALIDATIONS & CONSTRAINTS TESTS
    # ==========================================

    def test_requested_days_validation_range_1_to_30(self):
        self.client.login(username="student_alice", password="studentpassword123")

        # 0 days not allowed
        res_0 = self.client.post(reverse('circulation:create_request', args=[self.book1.pk]), {'requested_days': 0})
        self.assertFalse(BorrowRequest.objects.filter(member=self.student1, requested_days=0).exists())

        # Negative days not allowed
        res_neg = self.client.post(reverse('circulation:create_request', args=[self.book1.pk]), {'requested_days': -3})
        self.assertFalse(BorrowRequest.objects.filter(member=self.student1, requested_days=-3).exists())

        # More than 30 days not allowed
        res_31 = self.client.post(reverse('circulation:create_request', args=[self.book1.pk]), {'requested_days': 31})
        self.assertFalse(BorrowRequest.objects.filter(member=self.student1, requested_days=31).exists())

    def test_duplicate_pending_request_prevention(self):
        self.client.login(username="student_alice", password="studentpassword123")

        # First request succeeds
        res1 = self.client.post(reverse('circulation:create_request', args=[self.book1.pk]), {'requested_days': 5})
        self.assertEqual(res1.status_code, 302)
        self.assertEqual(BorrowRequest.objects.filter(member=self.student1, book=self.book1).count(), 1)

        # Second request for same book while first is Pending must be rejected
        res2 = self.client.post(reverse('circulation:create_request', args=[self.book1.pk]), {'requested_days': 10})
        self.assertEqual(BorrowRequest.objects.filter(member=self.student1, book=self.book1).count(), 1)

    def test_blocked_member_cannot_request_or_be_issued_books(self):
        # Blocked student tries to request
        self.client.login(username="student_blocked", password="blockedpassword123")
        res_req = self.client.post(reverse('circulation:create_request', args=[self.book1.pk]), {'requested_days': 5})
        self.assertFalse(BorrowRequest.objects.filter(member=self.blocked_student).exists())

        # Admin tries to issue book to blocked student
        self.client.login(username="head_librarian", password="adminpassword123")
        res_issue = self.client.post(reverse('circulation:issue_book'), {
            'member': self.blocked_student.pk,
            'book': self.book1.pk,
            'requested_days': 5,
            'issue_date': timezone.now().date().isoformat(),
        })
        self.assertEqual(res_issue.status_code, 200) # Re-renders form with error
        self.assertFalse(BorrowRecord.objects.filter(member=self.blocked_student).exists())

    def test_max_3_borrowed_books_limit_enforced(self):
        # Issue 3 books to student1
        for i in range(3):
            book = Book.objects.create(
                title=f"Book {i+1}",
                author="Author",
                isbn=f"978-00000000{i+10}",
                category=self.category,
                total_copies=2,
                available_copies=2
            )
            BorrowRecord.objects.create(
                book=book,
                member=self.student1,
                issued_by=self.librarian,
                requested_days=14,
                issue_date=timezone.now().date(),
                due_date=timezone.now().date() + timedelta(days=14),
                status=BorrowRecord.STATUS_ISSUED
            )

        # Student cannot submit another request (3 active loans reached)
        self.client.login(username="student_alice", password="studentpassword123")
        res_req = self.client.post(reverse('circulation:create_request', args=[self.book1.pk]), {'requested_days': 5})
        self.assertFalse(BorrowRequest.objects.filter(member=self.student1, book=self.book1).exists())

        # Admin cannot issue a 4th book
        self.client.login(username="head_librarian", password="adminpassword123")
        res_issue = self.client.post(reverse('circulation:issue_book'), {
            'member': self.student1.pk,
            'book': self.book1.pk,
            'requested_days': 5,
            'issue_date': timezone.now().date().isoformat(),
        })
        self.assertEqual(res_issue.status_code, 200) # Form error
        self.assertEqual(BorrowRecord.objects.filter(member=self.student1, status=BorrowRecord.STATUS_ISSUED).count(), 3)

    def test_cannot_issue_when_available_copies_is_zero(self):
        self.book_scarce.available_copies = 0
        self.book_scarce.save()

        self.client.login(username="head_librarian", password="adminpassword123")
        res = self.client.post(reverse('circulation:issue_book'), {
            'member': self.student1.pk,
            'book': self.book_scarce.pk,
            'requested_days': 5,
            'issue_date': timezone.now().date().isoformat(),
        })
        self.assertEqual(res.status_code, 200)
        self.assertFalse(BorrowRecord.objects.filter(member=self.student1, book=self.book_scarce).exists())
