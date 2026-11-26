from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from accounts.views import clearance_verification_hash
from circulation.models import Fine
from circulation.tests_institutional import make_loan
from circulation.tests_showcase import FAST_HASHER, make_book, make_member, make_staff


@FAST_HASHER
class ClearanceCertificateTests(TestCase):
    def setUp(self):
        self.staff = make_staff()
        self.member = make_member("alice")
        self.member.first_name, self.member.last_name = "Alice", "Rao"
        self.member.save()
        self.member.member_profile.department = "Physics"
        self.member.member_profile.save()
        self.url = reverse("accounts:clearance_certificate", args=[self.member.pk])
        self.book = make_book("9780000000030", "Optics", copies=3)

    def test_eligible_member_sees_certificate(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/clearance_certificate.html")
        today = timezone.now().date()
        self.assertContains(response, "Alice Rao")
        self.assertContains(response, "MEM-alice")
        self.assertContains(response, "Physics")
        self.assertContains(response, today.strftime("%d %B %Y"))
        self.assertContains(response, clearance_verification_hash(self.member.pk, today))
        self.assertContains(response, "Print Certificate")
        self.assertContains(response, "@media print")

    def test_missing_department_has_fallback(self):
        self.member.member_profile.department = ""
        self.member.member_profile.save()
        self.client.force_login(self.member)
        self.assertContains(self.client.get(self.url), "Not specified")

    def test_staff_may_view_member_certificate(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_other_member_forbidden(self):
        self.client.force_login(make_member("mallory"))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_non_member_target_is_404(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("accounts:clearance_certificate", args=[self.staff.pk]))
        self.assertEqual(response.status_code, 404)

    def test_active_loan_blocks_clearance(self):
        make_loan(self.book, self.member, self.staff)
        self.client.force_login(self.member)
        response = self.client.get(self.url, follow=True)
        self.assertRedirects(response, reverse("dashboard:member_dashboard"))
        self.assertContains(response, "1 active loan")
        self.assertTemplateNotUsed(response, "accounts/clearance_certificate.html")

    def test_unpaid_fine_blocks_clearance_and_staff_is_sent_to_member_page(self):
        loan = make_loan(self.book, self.member, self.staff, issued_days_ago=10, returned_days_ago=2)
        Fine.objects.create(
            borrow_record=loan, member=self.member, duration_days=8, overdue_days=0,
            amount=Decimal("220.00"), is_paid=False,
        )
        self.client.force_login(self.staff)
        response = self.client.get(self.url, follow=True)
        self.assertRedirects(response, reverse("accounts:member_detail", args=[self.member.pk]))
        self.assertContains(response, "pending fees of ₹220.00")

    def test_paid_fine_and_returned_loans_do_not_block(self):
        loan = make_loan(self.book, self.member, self.staff, issued_days_ago=10, returned_days_ago=2)
        Fine.objects.create(
            borrow_record=loan, member=self.member, duration_days=8, overdue_days=0,
            amount=Decimal("220.00"), is_paid=True,
        )
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_hash_depends_on_user_and_date_and_is_stable(self):
        day = date(2026, 11, 24)
        first = clearance_verification_hash(1, day)
        self.assertEqual(first, clearance_verification_hash(1, day))
        self.assertNotEqual(first, clearance_verification_hash(2, day))
        self.assertNotEqual(first, clearance_verification_hash(1, day + timedelta(days=1)))
        self.assertRegex(first, r"^[0-9A-F]{5}(-[0-9A-F]{5}){3}$")

    def test_dashboard_button_present_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("dashboard:member_dashboard"))
        self.assertContains(response, "Request Clearance Certificate")
        self.assertContains(response, self.url)

    def test_department_saved_from_profile_form(self):
        self.client.force_login(self.member)
        self.client.post(reverse("accounts:profile"), {
            "first_name": "Alice", "last_name": "Rao", "email": "a@example.com",
            "phone": "", "address": "", "department": "Chemistry",
        })
        self.member.member_profile.refresh_from_db()
        self.assertEqual(self.member.member_profile.department, "Chemistry")
