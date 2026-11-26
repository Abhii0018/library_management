from datetime import timedelta

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from books.models import Book, Category


class LandingMotionMarkupTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Physics")
        now = timezone.now()
        for index in range(14):
            book = Book.objects.create(
                title=f"Volume {index:02d}", author="Author", isbn=f"97800000100{index:02d}",
                total_copies=1, available_copies=1, category=self.category,
            )
            Book.objects.filter(pk=book.pk).update(added_date=now - timedelta(days=14 - index))

    def get(self):
        return self.client.get(reverse("dashboard:landing"))

    def test_shelf_rows_hold_newest_titles_first(self):
        response = self.get()
        rows = response.context["shelf_rows"]
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(len(row) <= 4 for row in rows))
        titles = [book["title"] for row in rows for book in row]
        self.assertEqual(titles[0], "Volume 13")
        self.assertEqual(len(titles), 12)
        self.assertNotIn("Volume 00", titles)

    def test_spines_link_to_book_detail_with_accessible_name(self):
        response = self.get()
        newest = Book.objects.get(title="Volume 13")
        self.assertContains(response, reverse("books:book_detail", args=[newest.pk]))
        self.assertContains(response, 'aria-label="Volume 13"')
        self.assertContains(response, 'class="spine spine-blank', count=None)

    def test_decorative_elements_hidden_from_assistive_tech(self):
        html = self.get().content.decode()
        self.assertIn('class="due-slip" aria-hidden="true"', html)
        self.assertIn('class="lifecycle-track" aria-hidden="true"', html)

    def test_titles_are_escaped_in_shelf_and_ticker(self):
        Book.objects.create(
            title="<script>alert(1)</script>", author="A", isbn="9780000999999",
            total_copies=1, available_copies=1, category=self.category,
        )
        html = self.get().content.decode()
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_ticker_has_duplicate_hidden_set_and_pause_control(self):
        html = self.get().content.decode()
        self.assertEqual(html.count('class="ticker-set"'), 2)
        self.assertIn('class="ticker-set" aria-hidden="true"', html)
        self.assertIn('id="motionToggle"', html)
        self.assertIn('aria-pressed="false"', html)

    def test_ticker_omitted_without_content(self):
        Book.objects.all().delete()
        Category.objects.all().delete()
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "landing-ticker")
        self.assertEqual(response.context["shelf_rows"], [[], [], []])

    def test_motion_gate_and_failsafe_present_before_content(self):
        html = self.get().content.decode()
        self.assertIn("prefers-reduced-motion: reduce", html)
        self.assertIn("motion-ready", html)
        self.assertLess(html.index("js-motion"), html.index("<body"))

    def test_pinned_section_has_block_wrapper(self):
        html = self.get().content.decode()
        self.assertIn('class="lifecycle-pin-scope"', html)
        self.assertLess(html.index("lifecycle-pin-scope"), html.index('id="how-it-works"'))

    def test_script_load_order(self):
        html = self.get().content.decode()
        order = [
            "vendor/gsap.min.js", "vendor/ScrollTrigger.min.js", "vendor/SplitText.min.js",
            "vendor/MotionPathPlugin.min.js", "vendor/DrawSVGPlugin.min.js",
            "js/motion.js", "js/landing-motion.js",
        ]
        positions = [html.index(name) for name in order]
        self.assertEqual(positions, sorted(positions))

    def test_vendored_assets_exist_and_are_nonempty(self):
        for name in ("gsap", "ScrollTrigger", "SplitText", "MotionPathPlugin", "DrawSVGPlugin"):
            path = finders.find(f"js/vendor/{name}.min.js")
            self.assertIsNotNone(path, name)
            with open(path, "rb") as handle:
                self.assertGreater(len(handle.read()), 1000, name)
        self.assertIsNotNone(finders.find("js/landing-motion.js"))

    def test_no_external_motion_cdn(self):
        html = self.get().content.decode()
        self.assertNotIn("cdn.jsdelivr.net/npm/gsap", html)
        self.assertNotIn("cdnjs.cloudflare.com/ajax/libs/gsap", html)
