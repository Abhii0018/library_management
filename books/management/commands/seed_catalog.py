import json
import os
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.conf import settings
from books.models import Book, Category


class Command(BaseCommand):
    help = "Seed the library catalog with verified academic and literary holdings."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate catalog population without writing to the database.'
        )
        parser.add_argument(
            '--dataset',
            type=str,
            default=os.path.join(settings.BASE_DIR, 'books', 'data', 'catalog_dataset.json'),
            help='Path to the curated catalog dataset JSON file.'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        dataset_path = options['dataset']

        if not os.path.exists(dataset_path):
            self.stderr.write(self.style.ERROR(f"Dataset file not found at: {dataset_path}"))
            return

        with open(dataset_path, 'r', encoding='utf-8') as f:
            try:
                catalog_data = json.load(f)
            except json.JSONDecodeError as e:
                self.stderr.write(self.style.ERROR(f"Invalid JSON in dataset file: {e}"))
                return

        mode_str = "[DRY-RUN] " if dry_run else ""
        self.stdout.write(self.style.NOTICE(f"{mode_str}Processing {len(catalog_data)} catalog entries from {dataset_path}..."))

        categories_cache = {c.name.lower(): c for c in Category.objects.all()}
        categories_created = 0

        books_created = 0
        books_updated = 0
        books_skipped = 0
        covers_linked = 0

        covers_dir = os.path.join(settings.BASE_DIR, 'static', 'images', 'covers')

        for item in catalog_data:
            cat_name = item.get('category', '').strip()
            cat_desc = item.get('category_description', '').strip()

            cat_key = cat_name.lower()
            category_obj = categories_cache.get(cat_key)

            if not category_obj:
                if dry_run:
                    self.stdout.write(f"{mode_str}Would create category: {cat_name}")
                    category_obj = Category(name=cat_name, description=cat_desc)
                else:
                    category_obj, created = Category.objects.get_or_create(
                        name=cat_name,
                        defaults={'description': cat_desc}
                    )
                    if created:
                        categories_created += 1
                categories_cache[cat_key] = category_obj

            raw_isbn = item.get('isbn', '').strip()
            clean_isbn = raw_isbn.replace('-', '').strip()
            title = item.get('title', '').strip()
            author = item.get('author', '').strip()

            existing_book = None
            if clean_isbn:
                # Check for existing book by formatted or unformatted ISBN
                existing_book = Book.objects.filter(isbn=raw_isbn).first()
                if not existing_book:
                    existing_book = Book.objects.filter(isbn=clean_isbn).first()
                if not existing_book:
                    for b in Book.objects.all():
                        if b.isbn.replace('-', '').strip() == clean_isbn:
                            existing_book = b
                            break

            if not existing_book and title and author:
                existing_book = Book.objects.filter(title__iexact=title, author__iexact=author).first()

            # Determine cover image availability in local static cache
            cover_path = ""
            local_cover_filename = f"{clean_isbn}.jpg"
            full_cover_path = os.path.join(covers_dir, local_cover_filename)
            if os.path.exists(full_cover_path) and os.path.getsize(full_cover_path) > 1000:
                cover_path = f"images/covers/{local_cover_filename}"

            total_copies = item.get('total_copies', 3)
            available_copies = item.get('available_copies', total_copies)
            book_value = Decimal(str(item.get('book_value', 500.00)))
            shelf_location = item.get('shelf_location', '')
            description = item.get('description', '')
            publisher = item.get('publisher', '')
            publication_year = item.get('publication_year')
            edition = item.get('edition', '')
            language = item.get('language', 'English')
            page_count = item.get('page_count')

            if existing_book:
                needs_save = False

                # Enrich missing metadata without overwriting custom administrator values
                if not existing_book.publisher and publisher:
                    existing_book.publisher = publisher
                    needs_save = True
                if not existing_book.publication_year and publication_year:
                    existing_book.publication_year = publication_year
                    needs_save = True
                if not existing_book.edition and edition:
                    existing_book.edition = edition
                    needs_save = True
                if not existing_book.page_count and page_count:
                    existing_book.page_count = page_count
                    needs_save = True
                if not existing_book.language and language:
                    existing_book.language = language
                    needs_save = True
                if (not existing_book.description or len(existing_book.description) < len(description)) and description:
                    existing_book.description = description
                    needs_save = True
                if not existing_book.cover_image and cover_path:
                    existing_book.cover_image = cover_path
                    needs_save = True
                    covers_linked += 1
                if not existing_book.category and category_obj:
                    existing_book.category = category_obj
                    needs_save = True
                if not existing_book.shelf_location and shelf_location:
                    existing_book.shelf_location = shelf_location
                    needs_save = True

                if needs_save:
                    if dry_run:
                        self.stdout.write(f"{mode_str}Would enrich metadata for existing title: {existing_book.title} ({existing_book.isbn})")
                    else:
                        existing_book.save()
                    books_updated += 1
                else:
                    books_skipped += 1
            else:
                if dry_run:
                    self.stdout.write(f"{mode_str}Would create new book: {title} by {author} ({raw_isbn})")
                else:
                    new_book = Book.objects.create(
                        title=title,
                        author=author,
                        isbn=raw_isbn,
                        category=category_obj,
                        total_copies=total_copies,
                        available_copies=available_copies,
                        shelf_location=shelf_location,
                        book_value=book_value,
                        description=description,
                        publisher=publisher,
                        publication_year=publication_year,
                        edition=edition,
                        language=language,
                        page_count=page_count,
                        cover_image=cover_path
                    )
                    if cover_path:
                        covers_linked += 1
                books_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"{mode_str}Catalog population complete:\n"
            f" - Categories created: {categories_created}\n"
            f" - Books created: {books_created}\n"
            f" - Books updated: {books_updated}\n"
            f" - Books skipped (unchanged): {books_skipped}\n"
            f" - Cover assets linked: {covers_linked}\n"
            f" - Total books now in catalog: {Book.objects.count() if not dry_run else 'N/A'}"
        ))
