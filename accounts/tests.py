from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, MemberProfile


class AccountsTestCase(TestCase):
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
            membership_id="MEM-99999",
            max_books_allowed=3
        )
        self.client = Client()

    def test_user_roles(self):
        self.assertTrue(self.librarian.is_librarian)
        self.assertFalse(self.librarian.is_member)
        self.assertTrue(self.member.is_member)
        self.assertFalse(self.member.is_librarian)

    def test_member_registration(self):
        response = self.client.post(reverse('accounts:register'), {
            'username': 'new_member',
            'email': 'new@member.com',
            'first_name': 'New',
            'last_name': 'Student',
            'password': 'password123',
            'confirm_password': 'password123',
            'phone': '1234567890',
            'address': 'Dorm 4'
        })
        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(username='new_member')
        self.assertEqual(new_user.role, User.ROLE_MEMBER)
        self.assertTrue(hasattr(new_user, 'member_profile'))
        self.assertTrue(new_user.member_profile.membership_id.startswith('MEM-'))

    def test_role_based_access_control(self):
        # Member tries to access librarian member list
        self.client.login(username="test_member", password="password123")
        response = self.client.get(reverse('accounts:member_list'))
        # Should be redirected to member dashboard with error
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dashboard:member_dashboard'), response.url)

        # Librarian accesses member list
        self.client.login(username="test_librarian", password="password123")
        response = self.client.get(reverse('accounts:member_list'))
        self.assertEqual(response.status_code, 200)

    def test_block_unblock_member(self):
        self.client.login(username="test_librarian", password="password123")
        self.assertFalse(self.profile.is_blocked)
        response = self.client.post(reverse('accounts:member_toggle_block', args=[self.member.pk]))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_blocked)
