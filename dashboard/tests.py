from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, MemberProfile
from books.models import Category, Book


class DashboardTestCase(TestCase):
    def setUp(self):
        self.librarian = User.objects.create_user(
            username="dash_librarian",
            password="password123",
            role=User.ROLE_LIBRARIAN
        )
        self.member = User.objects.create_user(
            username="dash_member",
            password="password123",
            role=User.ROLE_MEMBER
        )
        self.profile = MemberProfile.objects.create(
            user=self.member,
            membership_id="MEM-77777"
        )
        self.category = Category.objects.create(name="Fiction")
        self.book = Book.objects.create(
            title="Great Expectations",
            author="Charles Dickens",
            isbn="978-0141439563",
            category=self.category,
            total_copies=3,
            available_copies=3
        )
        self.client = Client()

    def test_dashboard_redirect_based_on_role(self):
        # Librarian redirect
        self.client.login(username="dash_librarian", password="password123")
        response = self.client.get(reverse('dashboard:index'))
        self.assertRedirects(response, reverse('dashboard:librarian_dashboard'))

        # Member redirect
        self.client.login(username="dash_member", password="password123")
        response = self.client.get(reverse('dashboard:index'))
        self.assertRedirects(response, reverse('dashboard:member_dashboard'))

    def test_librarian_dashboard_view(self):
        self.client.login(username="dash_librarian", password="password123")
        response = self.client.get(reverse('dashboard:librarian_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Librarian Dashboard")
        self.assertContains(response, "Total Titles")

    def test_member_dashboard_view(self):
        self.client.login(username="dash_member", password="password123")
        response = self.client.get(reverse('dashboard:member_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Library Dashboard")
        self.assertContains(response, "MEM-77777")

    def test_unauthenticated_landing_page_view(self):
        # When not logged in, visiting '/' renders landing page
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "LibriCore")
        self.assertContains(response, "Digital Athenaeum")
        self.assertContains(response, "Great Expectations")

        # Explicit welcome path also works
        response = self.client.get(reverse('dashboard:landing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "How Digital Borrowing Works")

