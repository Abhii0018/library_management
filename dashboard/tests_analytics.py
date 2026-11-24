from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from books.models import Category
from circulation.models import BorrowRecord
from circulation.tests_institutional import make_loan
from circulation.tests_showcase import FAST_HASHER, make_book, make_member, make_staff
from dashboard.views import _build_circulation_analytics, _month_starts


@FAST_HASHER
class CirculationAnalyticsTests(TestCase):
    def setUp(self):
        self.staff = make_staff()
        self.member = make_member("alice")
        self.today = timezone.now().date()

    def test_empty_database(self):
        data = _build_circulation_analytics(self.today)
        self.assertEqual(data["categories"], {"labels": [], "values": []})
        self.assertEqual(data["status"]["values"], [0, 0, 0, 0])
        self.assertEqual(sum(data["monthly"]["active"]), 0)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("dashboard:staff_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No loans recorded yet.")

    def test_top_five_categories_ordered_and_uncategorised(self):
        loans_per_category = {"A": 6, "B": 5, "C": 4, "D": 3, "E": 2, "F": 1}
        for name, loans in loans_per_category.items():
            category = Category.objects.create(name=name)
            book = make_book(f"isbn-{name}", f"Title {name}", copies=20, category=category)
            for _ in range(loans):
                make_loan(book, self.member, self.staff, returned_days_ago=0)
        loose = make_book("isbn-none", "No Category", copies=5)
        make_loan(loose, self.member, self.staff, returned_days_ago=0)

        data = _build_circulation_analytics(self.today)
        self.assertEqual(data["categories"]["labels"], ["A", "B", "C", "D", "E"])
        self.assertEqual(data["categories"]["values"], [6, 5, 4, 3, 2])

    def test_uncategorised_label(self):
        book = make_book("isbn-x", "Loose", copies=3)
        make_loan(book, self.member, self.staff, returned_days_ago=0)
        data = _build_circulation_analytics(self.today)
        self.assertEqual(data["categories"]["labels"], ["Uncategorised"])

    def test_status_counts(self):
        book = make_book("isbn-s", "Status", copies=20)
        make_loan(book, self.member, self.staff, issued_days_ago=2, term_days=14)
        make_loan(book, self.member, self.staff, issued_days_ago=30, term_days=7)
        make_loan(book, self.member, self.staff, issued_days_ago=20, term_days=14, returned_days_ago=10)
        make_loan(book, self.member, self.staff, issued_days_ago=20, term_days=3, returned_days_ago=10)
        data = _build_circulation_analytics(self.today)
        self.assertEqual(data["status"]["labels"], ["Active on Loan", "Returned on Time", "Returned Late", "Overdue"])
        self.assertEqual(data["status"]["values"], [1, 1, 1, 1])
        self.assertEqual(sum(data["status"]["values"]), BorrowRecord.objects.count())

    def test_monthly_series_covers_six_months_with_zero_fill(self):
        book = make_book("isbn-m", "Monthly", copies=20)
        make_loan(book, self.member, self.staff, issued_days_ago=0)
        make_loan(book, self.member, self.staff, issued_days_ago=400, term_days=7)
        data = _build_circulation_analytics(self.today)
        self.assertEqual(len(data["monthly"]["labels"]), 6)
        self.assertEqual(data["monthly"]["labels"][-1], self.today.strftime("%b %Y"))
        self.assertEqual(data["monthly"]["active"][-1], 1)
        self.assertEqual(sum(data["monthly"]["overdue"]), 0)

    def test_month_starts_handles_year_boundary(self):
        from datetime import date
        self.assertEqual(
            _month_starts(date(2026, 2, 15), 4),
            [date(2025, 11, 1), date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)],
        )

    def test_dashboard_embeds_json_and_chart_js(self):
        book = make_book("isbn-j", "Json </script> Title", copies=3)
        make_loan(book, self.member, self.staff, returned_days_ago=0)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("dashboard:staff_dashboard"))
        self.assertContains(response, 'id="circulation-analytics-data"')
        self.assertContains(response, "cdn.jsdelivr.net/npm/chart.js")
        self.assertContains(response, 'id="categoryChart"')
        self.assertContains(response, 'id="monthlyChart"')
        self.assertContains(response, "Academic Category Distribution")
        self.assertContains(response, "Monthly Circulation Status")
        self.assertEqual(response.context["circulation_analytics"]["status"]["values"][1], 1)

    def test_json_is_script_safe(self):
        category = Category.objects.create(name="</script><b>x")
        book = make_book("isbn-k", "Safe", copies=3, category=category)
        make_loan(book, self.member, self.staff, returned_days_ago=0)
        self.client.force_login(self.staff)
        html = self.client.get(reverse("dashboard:staff_dashboard")).content.decode()
        self.assertNotIn("</script><b>x", html)

    def test_all_management_dashboards_render(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("dashboard:staff_dashboard")).status_code, 200)
