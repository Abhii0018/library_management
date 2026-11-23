from django.test import TestCase, Client
from django.urls import reverse
from django.core.management import call_command
from django.core.exceptions import ValidationError
from accounts.models import User
from books.models import Category, Book


class BooksTestCase(TestCase):
    def setUp(self):
        self.librarian = User.objects.create_user(
            username="lib_user",
            password="password123",
            role=User.ROLE_LIBRARIAN
        )
        self.category = Category.objects.create(name="Science")
        self.book = Book.objects.create(
            title="Physics Principles",
            author="Halliday",
            isbn="978-1118230725",
            category=self.category,
            total_copies=5,
            available_copies=5,
            publisher="Wiley",
            publication_year=2013,
            edition="10th Edition",
            language="English",
            page_count=1200,
            cover_image="images/covers/9781118230725.jpg",
        )
        self.client = Client()

    def test_book_copies_validation(self):
        invalid_book = Book(
            title="Invalid",
            author="Author",
            isbn="1234567890",
            total_copies=2,
            available_copies=3
        )
        with self.assertRaises(ValidationError):
            invalid_book.clean()

    def test_book_search_and_filter(self):
        self.client.login(username="lib_user", password="password123")
        response = self.client.get(reverse('books:book_list') + '?q=Physics')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Physics Principles")

        response = self.client.get(reverse('books:book_list') + '?q=Nonexistent')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Physics Principles")

    def test_book_crud_by_librarian(self):
        self.client.login(username="lib_user", password="password123")
        response = self.client.post(reverse('books:book_create'), {
            'title': 'Operating Systems',
            'author': 'Silberschatz',
            'isbn': '978-1118063330',
            'category': self.category.pk,
            'total_copies': 3,
            'available_copies': 3,
            'publisher': 'Wiley',
            'publication_year': 2018,
            'edition': '10th Edition',
            'language': 'English',
            'page_count': 976,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Book.objects.filter(isbn='978-1118063330').exists())
        created_book = Book.objects.get(isbn='978-1118063330')
        self.assertEqual(created_book.publisher, 'Wiley')
        self.assertEqual(created_book.publication_year, 2018)

    def test_book_detail_metadata_view(self):
        self.client.login(username="lib_user", password="password123")
        response = self.client.get(reverse('books:book_detail', args=[self.book.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wiley")
        self.assertContains(response, "2013")
        self.assertContains(response, "10th Edition")
        self.assertContains(response, "1200 pages")
        self.assertContains(response, "images/covers/9781118230725.jpg")

    def test_seed_catalog_command_and_idempotency(self):
        call_command('seed_catalog')
        self.assertGreaterEqual(Book.objects.count(), 80)
        self.assertGreaterEqual(Category.objects.count(), 10)

        initial_count = Book.objects.count()
        call_command('seed_catalog')
        self.assertEqual(Book.objects.count(), initial_count)

    def test_catalog_pagination_and_sorting(self):
        call_command('seed_catalog')
        self.client.login(username="lib_user", password="password123")

        response = self.client.get(reverse('books:book_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['books']), 15)
        self.assertTrue(response.context['page_obj'].has_next())

        response_p2 = self.client.get(reverse('books:book_list') + '?page=2')
        self.assertEqual(response_p2.status_code, 200)
        self.assertEqual(len(response_p2.context['books']), 15)

        response_sort = self.client.get(reverse('books:book_list') + '?sort=title')
        self.assertEqual(response_sort.status_code, 200)
        titles = [b.title for b in response_sort.context['books']]
        self.assertEqual(titles, sorted(titles, key=lambda t: t.lower()))
