from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, MemberProfile
from books.models import Category, Book
from circulation.models import BorrowRecord, Fine


class FunctionalRulesVerificationTests(TestCase):
    """
    Complete verification tests covering all 18 functional requirements specified in the user prompt.
    """

    def setUp(self):
        # Create Librarian
        self.librarian = User.objects.create_user(
            username="test_librarian",
            password="adminpassword123",
            role=User.ROLE_LIBRARIAN,
            email="librarian@library.com"
        )

        # Create Student 1 (active)
        self.student1 = User.objects.create_user(
            username="student_rahul",
            password="studentpassword123",
            role=User.ROLE_MEMBER,
            email="rahul@student.edu",
            first_name="Rahul",
            last_name="Sharma"
        )
        self.profile1 = MemberProfile.objects.create(
            user=self.student1,
            membership_id="MEM-10001",
            max_books_allowed=3,
            is_blocked=False
        )

        # Create Student 2 (for cross-user isolation test)
        self.student2 = User.objects.create_user(
            username="student_priya",
            password="studentpassword123",
            role=User.ROLE_MEMBER,
            email="priya@student.edu",
            first_name="Priya",
            last_name="Patel"
        )
        self.profile2 = MemberProfile.objects.create(
            user=self.student2,
            membership_id="MEM-10002",
            max_books_allowed=3,
            is_blocked=False
        )

        # Create Category and Books
        self.category = Category.objects.create(name="Computer Science")
        self.book1 = Book.objects.create(
            title="Clean Code",
            author="Robert C. Martin",
            isbn="978-0132350884",
            category=self.category,
            total_copies=3,
            available_copies=3,
            shelf_location="CS-01"
        )
        self.book2 = Book.objects.create(
            title="Introduction to Algorithms",
            author="CLRS",
            isbn="978-0262033848",
            category=self.category,
            total_copies=2,
            available_copies=2,
            shelf_location="CS-02"
        )
        self.book3 = Book.objects.create(
            title="Design Patterns",
            author="Gang of Four",
            isbn="978-0201633610",
            category=self.category,
            total_copies=1,
            available_copies=1,
            shelf_location="CS-03"
        )
        self.book4 = Book.objects.create(
            title="Refactoring",
            author="Martin Fowler",
            isbn="978-0201485677",
            category=self.category,
            total_copies=2,
            available_copies=2,
            shelf_location="CS-04"
        )

        self.client = Client()

    # 1. Student login
    def test_01_student_login(self):
        login_success = self.client.login(username="student_rahul", password="studentpassword123")
        self.assertTrue(login_success)
        response = self.client.get(reverse('dashboard:index'))
        self.assertRedirects(response, reverse('dashboard:member_dashboard'))

    # 2. Librarian login
    def test_02_librarian_login(self):
        login_success = self.client.login(username="test_librarian", password="adminpassword123")
        self.assertTrue(login_success)
        response = self.client.get(reverse('dashboard:index'))
        self.assertRedirects(response, reverse('dashboard:librarian_dashboard'))

    # 3. Student browses books
    def test_03_student_browses_books(self):
        self.client.login(username="student_rahul", password="studentpassword123")
        response = self.client.get(reverse('books:book_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clean Code")
        self.assertContains(response, "Introduction to Algorithms")
        # Student does NOT see Add New Book management button
        self.assertNotContains(response, "Add New Book")

    # 4. Student views book details
    def test_04_student_views_book_details(self):
        self.client.login(username="student_rahul", password="studentpassword123")
        response = self.client.get(reverse('books:book_detail', args=[self.book1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clean Code")
        self.assertContains(response, "978-0132350884")
        self.assertContains(response, "In Stock")
        # Student does NOT see Edit Book or Delete Book buttons
        self.assertNotContains(response, "Edit Book")
        self.assertNotContains(response, "Delete Book")

    # 5. Librarian adds a book
    def test_05_librarian_adds_a_book(self):
        self.client.login(username="test_librarian", password="adminpassword123")
        response = self.client.post(reverse('books:book_create'), {
            'title': 'The Pragmatic Programmer',
            'author': 'Andy Hunt & Dave Thomas',
            'isbn': '978-0201616224',
            'category': self.category.pk,
            'total_copies': 4,
            'available_copies': 4,
            'shelf_location': 'CS-05',
            'description': 'From journeyman to master'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Book.objects.filter(isbn='978-0201616224').exists())

    # 6. Librarian edits a book
    def test_06_librarian_edits_a_book(self):
        self.client.login(username="test_librarian", password="adminpassword123")
        response = self.client.post(reverse('books:book_edit', args=[self.book1.pk]), {
            'title': 'Clean Code: A Handbook of Agile Software Craftsmanship',
            'author': 'Robert C. Martin',
            'isbn': '978-0132350884',
            'category': self.category.pk,
            'total_copies': 5,
            'available_copies': 5,
            'shelf_location': 'CS-01-A',
        })
        self.assertEqual(response.status_code, 302)
        self.book1.refresh_from_db()
        self.assertEqual(self.book1.total_copies, 5)
        self.assertEqual(self.book1.available_copies, 5)

    # 7 & 8 & 9. Librarian issues a book -> available copies decrease -> student sees on dashboard
    def test_07_08_09_issue_book_and_verify_copies_and_dashboard(self):
        self.client.login(username="test_librarian", password="adminpassword123")
        today = timezone.now().date()
        due_date = today + timedelta(days=14)

        initial_available = self.book1.available_copies
        response = self.client.post(reverse('circulation:issue_book'), {
            'member': self.student1.pk,
            'book': self.book1.pk,
            'issue_date': today.isoformat(),
            'due_date': due_date.isoformat(),
            'notes': 'Issued for semester study',
        })
        self.assertEqual(response.status_code, 302)

        # 8. Available copies decrease
        self.book1.refresh_from_db()
        self.assertEqual(self.book1.available_copies, initial_available - 1)

        # 9. Student sees the issued book on their dashboard
        self.client.login(username="student_rahul", password="studentpassword123")
        dash_response = self.client.get(reverse('dashboard:member_dashboard'))
        self.assertEqual(dash_response.status_code, 200)
        self.assertContains(dash_response, "Clean Code")
        self.assertContains(dash_response, due_date.strftime("%b"))

    # 10 & 11 & 12. Librarian returns the book -> available copies increase -> student sees in history
    def test_10_11_12_return_book_and_verify_history(self):
        # Create active loan
        today = timezone.now().date()
        loan = BorrowRecord.objects.create(
            book=self.book1,
            member=self.student1,
            issued_by=self.librarian,
            issue_date=today - timedelta(days=5),
            due_date=today + timedelta(days=9),
            status=BorrowRecord.STATUS_ISSUED
        )
        self.book1.available_copies = 2
        self.book1.save()

        # Librarian returns
        self.client.login(username="test_librarian", password="adminpassword123")
        return_response = self.client.post(reverse('circulation:return_book', args=[loan.pk]), {
            'return_date': today.isoformat(),
            'notes': 'Book in great condition'
        })
        self.assertEqual(return_response.status_code, 302)

        # 11. Available copies increase
        self.book1.refresh_from_db()
        self.assertEqual(self.book1.available_copies, 3)

        loan.refresh_from_db()
        self.assertEqual(loan.status, BorrowRecord.STATUS_RETURNED)
        self.assertEqual(loan.return_date, today)

        # 12. Student sees the returned book in history page and dashboard reflects 0 active
        self.client.login(username="student_rahul", password="studentpassword123")
        history_response = self.client.get(reverse('circulation:member_history'))
        self.assertEqual(history_response.status_code, 200)
        self.assertContains(history_response, "Clean Code")
        self.assertContains(history_response, today.strftime("%b"))

        dash_response = self.client.get(reverse('dashboard:member_dashboard'))
        self.assertEqual(dash_response.status_code, 200)
        self.assertContains(dash_response, "0 / 3")

    # 13. Late return calculates correct fine (Section 16: 6 days = ₹160)
    def test_13_late_return_calculates_correct_fine(self):
        issue = date(2026, 10, 10)
        due = date(2026, 10, 15)
        ret = date(2026, 10, 16)
        loan = BorrowRecord.objects.create(
            book=self.book1,
            member=self.student1,
            issued_by=self.librarian,
            issue_date=issue,
            due_date=due,
            status=BorrowRecord.STATUS_ISSUED
        )
        self.book1.available_copies = 2
        self.book1.save()

        self.client.login(username="test_librarian", password="adminpassword123")
        response = self.client.post(reverse('circulation:return_book', args=[loan.pk]), {
            'return_date': ret.isoformat(),
            'notes': '1 day late (6 days duration)'
        })
        self.assertEqual(response.status_code, 302)

        fine = Fine.objects.get(borrow_record=loan)
        self.assertEqual(fine.duration_days, 6)
        self.assertEqual(fine.amount, Decimal('160.00'))
        self.assertFalse(fine.is_paid)

    # 14. Student with 3 active books cannot receive a 4th book
    def test_14_max_borrowing_limit_enforced(self):
        today = timezone.now().date()
        due = today + timedelta(days=14)

        # Create 3 active loans for student1
        BorrowRecord.objects.create(book=self.book1, member=self.student1, issued_by=self.librarian, issue_date=today, due_date=due, status=BorrowRecord.STATUS_ISSUED)
        BorrowRecord.objects.create(book=self.book2, member=self.student1, issued_by=self.librarian, issue_date=today, due_date=due, status=BorrowRecord.STATUS_ISSUED)
        BorrowRecord.objects.create(book=self.book3, member=self.student1, issued_by=self.librarian, issue_date=today, due_date=due, status=BorrowRecord.STATUS_ISSUED)

        self.client.login(username="test_librarian", password="adminpassword123")
        # Attempt to issue 4th book
        response = self.client.post(reverse('circulation:issue_book'), {
            'member': self.student1.pk,
            'book': self.book4.pk,
            'issue_date': today.isoformat(),
            'due_date': due.isoformat(),
        })
        # Must be rejected
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maximum borrowing limit reached. You cannot borrow another book until one is returned.")
        self.assertFalse(BorrowRecord.objects.filter(member=self.student1, book=self.book4).exists())

    # 15. Blocked student cannot receive a new book
    def test_15_blocked_student_rejected(self):
        self.profile1.is_blocked = True
        self.profile1.save()

        today = timezone.now().date()
        due = today + timedelta(days=14)

        self.client.login(username="test_librarian", password="adminpassword123")
        response = self.client.post(reverse('circulation:issue_book'), {
            'member': self.student1.pk,
            'book': self.book1.pk,
            'issue_date': today.isoformat(),
            'due_date': due.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "blocked")
        self.assertFalse(BorrowRecord.objects.filter(member=self.student1, book=self.book1).exists())

    # 16. Unavailable book cannot be issued
    def test_16_unavailable_book_cannot_be_issued(self):
        self.book1.available_copies = 0
        self.book1.save()

        today = timezone.now().date()
        due = today + timedelta(days=14)

        self.client.login(username="test_librarian", password="adminpassword123")
        response = self.client.post(reverse('circulation:issue_book'), {
            'member': self.student1.pk,
            'book': self.book1.pk,
            'issue_date': today.isoformat(),
            'due_date': due.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No copies currently available")
        self.assertFalse(BorrowRecord.objects.filter(member=self.student1, book=self.book1).exists())

    # 17. Student cannot access librarian pages directly
    def test_17_student_cannot_access_librarian_pages_directly(self):
        self.client.login(username="student_rahul", password="studentpassword123")

        librarian_urls = [
            '/books/add/',
            '/books/delete/',
            f'/books/{self.book1.pk}/edit/',
            f'/books/{self.book1.pk}/delete/',
            '/circulation/issue/',
            f'/circulation/return/{self.book1.pk}/',
            '/circulation/transactions/',
            '/circulation/fines/',
            '/accounts/members/',
            '/accounts/members/add/',
            f'/accounts/members/{self.student1.pk}/',
            '/dashboard/librarian/',
            # Direct aliases
            '/transactions/issue/',
            '/transactions/return/',
            '/members/',
            '/dashboard/admin/',
        ]

        for url in librarian_urls:
            response = self.client.get(url)
            # Rejection: must not return HTTP 200
            self.assertIn(
                response.status_code,
                [302, 403],
                f"Student was unexpectedly granted access to {url} (status: {response.status_code})"
            )

    # 18. Student cannot access another student's data
    def test_18_student_cannot_access_another_students_data(self):
        # Create loan and fine for Student 2
        loan2 = BorrowRecord.objects.create(
            book=self.book2,
            member=self.student2,
            issued_by=self.librarian,
            issue_date=date(2026, 9, 1),
            due_date=date(2026, 9, 15),
            return_date=date(2026, 9, 20),
            status=BorrowRecord.STATUS_RETURNED
        )
        fine2 = Fine.objects.create(
            borrow_record=loan2,
            member=self.student2,
            overdue_days=5,
            amount=Decimal('25.00'),
            is_paid=False
        )

        # Login as Student 1
        self.client.login(username="student_rahul", password="studentpassword123")

        # Student 1 views their dashboard
        response = self.client.get(reverse('dashboard:member_dashboard'))
        self.assertEqual(response.status_code, 200)

        # Student 1 must NOT see Student 2's data
        self.assertNotContains(response, "Introduction to Algorithms")
        self.assertNotContains(response, "MEM-10002")
        self.assertNotContains(response, "₹25.00")

        # Student 1 cannot view Student 2's member detail
        mem_response = self.client.get(reverse('accounts:member_detail', args=[self.student2.pk]))
        self.assertIn(mem_response.status_code, [302, 403])
