from datetime import date, timedelta
from django.core.management import call_command
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, MemberProfile, StaffProfile
from books.models import Category, Book
from circulation.models import BorrowRequest, BorrowRecord


class AuthAndRoleBasedAccessTestCase(TestCase):
    """
    Comprehensive tests for Backend Authentication and Role-Based Access Control:
    1. Idempotent initial Admin creation (setup_admin command) & login.
    2. Common login routing:
       - Admin -> Admin Dashboard
       - Staff -> Staff Dashboard
       - Member -> Member Dashboard
    3. Admin permissions & Staff Management (Create, View, Edit, Activate, Deactivate).
    4. Staff permissions (Operational access granted, Staff Management strictly denied).
    5. Deactivated staff login blocked while prior audit records remain intact.
    6. Member authentication & strict URL tampering isolation.
    """

    def setUp(self):
        self.client = Client()

        # Run setup_admin to create initial Admin account
        call_command('setup_admin')
        self.admin_user = User.objects.get(username='Abhiadmin@17')

        # Create Category & Book for circulation testing
        self.category = Category.objects.create(name="Computer Science")
        self.book = Book.objects.create(
            title="Clean Architecture",
            author="Robert C. Martin",
            isbn="978-0134494166",
            category=self.category,
            total_copies=5,
            available_copies=5
        )

        # Create a Member user
        self.member_user = User.objects.create_user(
            username="student_rahul",
            password="rahulpassword123",
            role=User.ROLE_MEMBER,
            email="rahul@student.edu",
            first_name="Rahul",
            last_name="Sharma"
        )
        self.member_profile = MemberProfile.objects.create(
            user=self.member_user,
            membership_id="MEM-88888",
            max_books_allowed=3,
            is_blocked=False
        )

    def test_01_initial_admin_setup_idempotency_and_login(self):
        # 1. Verify user attributes
        self.assertEqual(self.admin_user.username, 'Abhiadmin@17')
        self.assertTrue(self.admin_user.is_superuser)
        self.assertTrue(self.admin_user.is_staff)
        self.assertTrue(self.admin_user.is_admin_user)
        self.assertTrue(self.admin_user.is_librarian)
        self.assertTrue(self.admin_user.check_password('Abhi@17'))

        # 2. Re-run setup_admin to verify idempotency (no duplicates, no error)
        call_command('setup_admin')
        self.assertEqual(User.objects.filter(username='Abhiadmin@17').count(), 1)

        # 3. Common login as Admin
        response = self.client.post(reverse('accounts:login'), {
            'username': 'Abhiadmin@17',
            'password': 'Abhi@17'
        })
        self.assertRedirects(response, reverse('dashboard:admin_dashboard'))

        # Verify Admin Dashboard accessible
        dash_res = self.client.get(reverse('dashboard:admin_dashboard'))
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, "Admin Dashboard")
        self.assertContains(dash_res, "Staff Management")

    def test_02_admin_staff_management_lifecycle(self):
        # Login as Admin
        self.client.login(username='Abhiadmin@17', password='Abhi@17')

        # 1. View Staff List
        list_res = self.client.get(reverse('accounts:staff_list'))
        self.assertEqual(list_res.status_code, 200)
        self.assertContains(list_res, "Staff Management")
        self.assertContains(list_res, "Add Staff Member")

        # 2. Create Staff Member
        create_res = self.client.post(reverse('accounts:staff_create'), {
            'staff_id': 'STF-1001',
            'username': 'staff_priya',
            'first_name': 'Priya',
            'last_name': 'Verma',
            'email': 'priya@library.com',
            'phone': '9876543210',
            'department': 'Circulation',
            'password': 'PriyaStaff@123',
            'confirm_password': 'PriyaStaff@123',
            'is_active': True,
        })
        self.assertRedirects(create_res, reverse('accounts:staff_list'))

        staff_user = User.objects.get(username='staff_priya')
        self.assertEqual(staff_user.role, User.ROLE_STAFF)
        self.assertTrue(staff_user.is_staff_user)
        self.assertTrue(staff_user.is_librarian)
        self.assertFalse(staff_user.is_admin_user)
        self.assertEqual(staff_user.staff_profile.staff_id, 'STF-1001')
        self.assertTrue(staff_user.is_active)

        # 3. Edit Staff Member
        edit_res = self.client.post(reverse('accounts:staff_edit', args=[staff_user.pk]), {
            'staff_id': 'STF-1001',
            'first_name': 'Priyanka',
            'last_name': 'Verma',
            'email': 'priyanka@library.com',
            'phone': '9876543211',
            'department': 'Reference & Archiving',
            'is_active': True,
        })
        self.assertRedirects(edit_res, reverse('accounts:staff_list'))
        staff_user.refresh_from_db()
        self.assertEqual(staff_user.first_name, 'Priyanka')
        self.assertEqual(staff_user.staff_profile.department, 'Reference & Archiving')

        # 4. Toggle Staff Status (Deactivate)
        toggle_res = self.client.post(reverse('accounts:staff_toggle_status', args=[staff_user.pk]))
        self.assertRedirects(toggle_res, reverse('accounts:staff_list'))
        staff_user.refresh_from_db()
        self.assertFalse(staff_user.is_active)

        # 5. Toggle Staff Status (Reactivate)
        toggle_res2 = self.client.post(reverse('accounts:staff_toggle_status', args=[staff_user.pk]))
        self.assertRedirects(toggle_res2, reverse('accounts:staff_list'))
        staff_user.refresh_from_db()
        self.assertTrue(staff_user.is_active)

    def test_03_staff_login_and_permissions(self):
        # Create active Staff member
        staff_user = User.objects.create_user(
            username="staff_vikram",
            password="VikramPassword@123",
            role=User.ROLE_STAFF,
            is_staff=True,
            first_name="Vikram",
            last_name="Singh"
        )
        StaffProfile.objects.create(
            user=staff_user,
            staff_id="STF-2002",
            department="Circulation"
        )

        # 1. Staff logs in via common login page
        login_res = self.client.post(reverse('accounts:login'), {
            'username': 'staff_vikram',
            'password': 'VikramPassword@123'
        })
        # Must redirect to Staff Dashboard
        self.assertRedirects(login_res, reverse('dashboard:staff_dashboard'))

        # 2. Staff views Staff Dashboard
        dash_res = self.client.get(reverse('dashboard:staff_dashboard'))
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, "Staff Dashboard")
        self.assertNotContains(dash_res, "Staff Management")

        # 3. Staff can access operational library pages
        allowed_urls = [
            reverse('books:book_list'),
            reverse('accounts:member_list'),
            reverse('circulation:request_list'),
            reverse('circulation:admin_borrowed'),
            reverse('circulation:admin_history'),
            reverse('circulation:fine_list'),
            reverse('accounts:profile'),
        ]
        for url in allowed_urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Staff was incorrectly blocked from {url}")

        # 4. Staff CANNOT access Admin-only Staff Management
        forbidden_urls = [
            reverse('accounts:staff_list'),
            reverse('accounts:staff_create'),
            reverse('accounts:staff_edit', args=[staff_user.pk]),
            reverse('dashboard:admin_dashboard'),
        ]
        for url in forbidden_urls:
            res = self.client.get(url)
            # Backend decorator strictly redirects
            self.assertIn(res.status_code, [302, 403], f"Staff was unexpectedly allowed to access {url}")

    def test_04_deactivated_staff_cannot_login_and_records_remain_intact(self):
        # Create Staff member
        staff_user = User.objects.create_user(
            username="staff_rajesh",
            password="RajeshPassword@123",
            role=User.ROLE_STAFF,
            is_staff=True,
            is_active=True
        )
        StaffProfile.objects.create(
            user=staff_user,
            staff_id="STF-3003",
            department="Circulation"
        )

        # Create loan reviewed/issued by this staff member
        today = timezone.now().date()
        loan = BorrowRecord.objects.create(
            book=self.book,
            member=self.member_user,
            issued_by=staff_user,
            issue_date=today,
            due_date=today + timedelta(days=14),
            status=BorrowRecord.STATUS_ISSUED
        )
        self.assertEqual(loan.issued_by, staff_user)

        # Admin deactivates Rajesh
        staff_user.is_active = False
        staff_user.save()

        # Attempt to login as deactivated staff
        response = self.client.post(reverse('accounts:login'), {
            'username': 'staff_rajesh',
            'password': 'RajeshPassword@123'
        })
        # Must be rejected (stays on login page with error)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "deactivated")

        # Verify historical records are intact
        loan.refresh_from_db()
        self.assertEqual(loan.issued_by, staff_user)
        self.assertEqual(loan.issued_by.username, "staff_rajesh")

    def test_05_member_login_and_unauthorized_url_blocking(self):
        # 1. Member logs in via common login page
        response = self.client.post(reverse('accounts:login'), {
            'username': 'student_rahul',
            'password': 'rahulpassword123'
        })
        # Redirects to Member Dashboard
        self.assertRedirects(response, reverse('dashboard:member_dashboard'))

        # 2. Member Dashboard view
        dash_res = self.client.get(reverse('dashboard:member_dashboard'))
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, "My Library Dashboard")

        # 3. Member tries to access Staff & Admin URLs directly
        blocked_urls = [
            reverse('dashboard:admin_dashboard'),
            reverse('dashboard:staff_dashboard'),
            reverse('dashboard:librarian_dashboard'),
            reverse('accounts:staff_list'),
            reverse('accounts:staff_create'),
            reverse('accounts:member_list'),
            reverse('accounts:member_create'),
            reverse('books:book_create'),
            reverse('circulation:admin_borrowed'),
            reverse('circulation:admin_history'),
            reverse('circulation:request_list'),
        ]
        for url in blocked_urls:
            res = self.client.get(url)
            self.assertIn(
                res.status_code,
                [302, 403],
                f"Member was improperly granted access to {url} with code {res.status_code}"
            )
