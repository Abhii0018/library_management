from django.test import TestCase, Client
from django.urls import reverse
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
        )
        self.client = Client()

    def test_book_copies_validation(self):
        # Available copies cannot exceed total copies
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
        # Search by title
        response = self.client.get(reverse('books:book_list') + '?q=Physics')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Physics Principles")

        # Search with non-matching query
        response = self.client.get(reverse('books:book_list') + '?q=Nonexistent')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Physics Principles")

    def test_book_crud_by_librarian(self):
        self.client.login(username="lib_user", password="password123")
        # Add book
        response = self.client.post(reverse('books:book_create'), {
            'title': 'Operating Systems',
            'author': 'Silberschatz',
            'isbn': '978-1118063330',
            'category': self.category.pk,
            'total_copies': 3,
            'available_copies': 3,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Book.objects.filter(isbn='978-1118063330').exists())
