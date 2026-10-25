from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, MemberProfile
from books.models import Category, Book
from circulation.models import BorrowRecord, Fine


class CirculationTestCase(TestCase):
    def setUp(self):
        self.librarian = User.objects.create_user(
            username="test_librarian",
            password="password123",
            role=User.ROLE_LIBRARIAN
        )
        self.member = User.objects.create_user(
            username="test_member",
            password="password123",
            role=User.ROLE_MEMBER
        )
        self.profile = MemberProfile.objects.create(
            user=self.member,
            membership_id="MEM-11111",
            max_books_allowed=2,
            is_blocked=False
        )

        self.category = Category.objects.create(name="Tech")
        self.book = Book.objects.create(
            title="Clean Architecture",
            author="Robert C. Martin",
            isbn="978-0134494166",
            category=self.category,
            total_copies=2,
            available_copies=2
        )

        self.client = Client()
        self.client.login(username="test_librarian", password="password123")

    def test_issue_book_success(self):
        today = timezone.now().date()
        due = today + timedelta(days=14)

        response = self.client.post(reverse('circulation:issue_book'), {
            'member': self.member.pk,
            'book': self.book.pk,
            'issue_date': today.isoformat(),
            'due_date': due.isoformat(),
            'notes': 'First edition copy',
        })
        self.assertEqual(response.status_code, 302)

        # Check available copies decremented
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)

        # Check record created
        record = BorrowRecord.objects.get(member=self.member, book=self.book)
        self.assertEqual(record.status, BorrowRecord.STATUS_ISSUED)
        self.assertEqual(record.issued_by, self.librarian)

    def test_cannot_issue_when_available_copies_is_zero(self):
        self.book.available_copies = 0
        self.book.save()

        today = timezone.now().date()
        response = self.client.post(reverse('circulation:issue_book'), {
            'member': self.member.pk,
            'book': self.book.pk,
            'issue_date': today.isoformat(),
            'due_date': (today + timedelta(days=14)).isoformat(),
        })
        # Should stay on page with error
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BorrowRecord.objects.filter(member=self.member, book=self.book).exists())

    def test_cannot_issue_to_blocked_member(self):
        self.profile.is_blocked = True
        self.profile.save()

        today = timezone.now().date()
        response = self.client.post(reverse('circulation:issue_book'), {
            'member': self.member.pk,
            'book': self.book.pk,
            'issue_date': today.isoformat(),
            'due_date': (today + timedelta(days=14)).isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BorrowRecord.objects.filter(member=self.member).exists())

    def test_return_book_on_time_no_fine(self):
        today = timezone.now().date()
        issue_date = today - timedelta(days=2) # 2 days duration = FREE (₹0)
        due_date = today + timedelta(days=12)

        record = BorrowRecord.objects.create(
            book=self.book,
            member=self.member,
            issued_by=self.librarian,
            issue_date=issue_date,
            due_date=due_date,
            status=BorrowRecord.STATUS_ISSUED
        )
        self.book.available_copies = 1
        self.book.save()

        # Return today (2 days total duration: free)
        response = self.client.post(reverse('circulation:return_book', args=[record.pk]), {
            'return_date': today.isoformat(),
            'notes': 'Returned within 2 days free period'
        })
        self.assertEqual(response.status_code, 302)

        record.refresh_from_db()
        self.assertEqual(record.status, BorrowRecord.STATUS_RETURNED)
        self.assertEqual(record.return_date, today)

        # Inventory restored
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)

        # Free borrowing period applied: amount is 0
        fine = Fine.objects.get(borrow_record=record)
        self.assertEqual(fine.amount, Decimal('0.00'))
        self.assertTrue(fine.is_paid)

    def test_return_book_overdue_fine_calculation(self):
        # Section 16 Policy:
        # Issue: Oct 10, Return: Oct 16 => Duration 6 days => Fee = (6-2)*20 + 100 = ₹160
        issue_date = date(2026, 10, 10)
        due_date = date(2026, 10, 15)
        return_date = date(2026, 10, 16)

        record = BorrowRecord.objects.create(
            book=self.book,
            member=self.member,
            issued_by=self.librarian,
            issue_date=issue_date,
            due_date=due_date,
            status=BorrowRecord.STATUS_ISSUED
        )
        self.book.available_copies = 1
        self.book.save()

        response = self.client.post(reverse('circulation:return_book', args=[record.pk]), {
            'return_date': return_date.isoformat(),
            'notes': 'Returned 1 day late (6 days duration)'
        })
        self.assertEqual(response.status_code, 302)

        record.refresh_from_db()
        self.assertEqual(record.status, BorrowRecord.STATUS_RETURNED)

        # Fee verified: 6 days => ₹160
        fine = Fine.objects.get(borrow_record=record)
        self.assertEqual(fine.duration_days, 6)
        self.assertEqual(fine.amount, Decimal('160.00'))
        self.assertFalse(fine.is_paid)

        # Mark fee paid
        pay_response = self.client.post(reverse('circulation:mark_fine_paid', args=[fine.pk]))
        self.assertEqual(pay_response.status_code, 302)
        fine.refresh_from_db()
        self.assertTrue(fine.is_paid)
        self.assertIsNotNone(fine.paid_date)
