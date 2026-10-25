import random
from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User, MemberProfile
from books.models import Category, Book
from circulation.models import BorrowRecord, Fine


class Command(BaseCommand):
    help = "Seeds initial demo data including librarian, members, books, and transactions."

    def handle(self, *args, **options):
        self.stdout.write("Starting data seeding...")

        # 1. Create Librarian/Superuser
        librarian, created = User.objects.get_or_create(
            username="librarian",
            defaults={
                "email": "admin@library.com",
                "first_name": "Eleanor",
                "last_name": "Vance",
                "role": User.ROLE_LIBRARIAN,
                "is_staff": True,
                "is_superuser": True,
            }
        )
        if created:
            librarian.set_password("admin123")
            librarian.save()
            self.stdout.write(self.style.SUCCESS("Created Librarian/Admin: librarian / admin123"))
        else:
            self.stdout.write("Librarian 'librarian' already exists.")

        # 2. Create Members
        members_data = [
            {"username": "rahul", "first_name": "Rahul", "last_name": "Sharma", "email": "rahul@example.com", "phone": "9876543210"},
            {"username": "priya", "first_name": "Priya", "last_name": "Patel", "email": "priya@example.com", "phone": "9812345678"},
            {"username": "arjun", "first_name": "Arjun", "last_name": "Verma", "email": "arjun@example.com", "phone": "9723456789"},
            {"username": "sneha", "first_name": "Sneha", "last_name": "Reddy", "email": "sneha@example.com", "phone": "9934567890"},
        ]

        members = []
        for m_data in members_data:
            user, u_created = User.objects.get_or_create(
                username=m_data["username"],
                defaults={
                    "first_name": m_data["first_name"],
                    "last_name": m_data["last_name"],
                    "email": m_data["email"],
                    "role": User.ROLE_MEMBER,
                }
            )
            if u_created:
                user.set_password("member123")
                user.save()
                profile = MemberProfile.objects.create(
                    user=user,
                    membership_id=MemberProfile.generate_membership_id(),
                    phone=m_data["phone"],
                    address="University Campus Hostel",
                    max_books_allowed=3,
                    is_blocked=False,
                )
                self.stdout.write(self.style.SUCCESS(f"Created Member: {user.username} / member123 ({profile.membership_id})"))
            else:
                profile = user.member_profile
            members.append(user)

        # Block Sneha to demonstrate the blocked member feature
        if len(members) >= 4:
            sneha_profile = members[3].member_profile
            sneha_profile.is_blocked = True
            sneha_profile.save()
            self.stdout.write(self.style.WARNING("Blocked member 'sneha' for testing block enforcement."))

        # 3. Create Categories
        categories_data = [
            ("Computer Science", "Programming, algorithms, systems, and software engineering."),
            ("Literature & Fiction", "Classic and modern works of literature, novels, and stories."),
            ("Mathematics", "Calculus, linear algebra, statistics, and discrete structures."),
            ("History & Politics", "World history, political theory, and historical biographies."),
            ("Science", "Physics, chemistry, astronomy, and biology."),
        ]

        categories = {}
        for cat_name, cat_desc in categories_data:
            cat, _ = Category.objects.get_or_create(name=cat_name, defaults={"description": cat_desc})
            categories[cat_name] = cat

        # 4. Create Books
        books_data = [
            {
                "title": "Clean Code",
                "author": "Robert C. Martin",
                "isbn": "978-0132350884",
                "category": categories["Computer Science"],
                "total_copies": 5,
                "available_copies": 3,
                "shelf_location": "CS-01",
                "description": "A handbook of agile software craftsmanship with best practices and refactoring techniques.",
            },
            {
                "title": "Introduction to Algorithms (CLRS)",
                "author": "Thomas H. Cormen",
                "isbn": "978-0262033848",
                "category": categories["Computer Science"],
                "total_copies": 4,
                "available_copies": 3,
                "shelf_location": "CS-02",
                "description": "The definitive comprehensive reference on modern computer algorithms and data structures.",
            },
            {
                "title": "Design Patterns: Gang of Four",
                "author": "Erich Gamma et al.",
                "isbn": "978-0201633610",
                "category": categories["Computer Science"],
                "total_copies": 3,
                "available_copies": 2,
                "shelf_location": "CS-03",
                "description": "Elements of reusable object-oriented software design.",
            },
            {
                "title": "To Kill a Mockingbird",
                "author": "Harper Lee",
                "isbn": "978-0446310786",
                "category": categories["Literature & Fiction"],
                "total_copies": 3,
                "available_copies": 2,
                "shelf_location": "LIT-01",
                "description": "Pulitzer prize-winning novel exploring racial injustice in the American South.",
            },
            {
                "title": "1984",
                "author": "George Orwell",
                "isbn": "978-0451524935",
                "category": categories["Literature & Fiction"],
                "total_copies": 4,
                "available_copies": 4,
                "shelf_location": "LIT-02",
                "description": "Classic dystopian novel describing surveillance, authoritarianism, and truth manipulation.",
            },
            {
                "title": "Linear Algebra and Its Applications",
                "author": "Gilbert Strang",
                "isbn": "978-0030105678",
                "category": categories["Mathematics"],
                "total_copies": 3,
                "available_copies": 3,
                "shelf_location": "MATH-01",
                "description": "Comprehensive introduction to matrix theory, eigenvalues, and vectors.",
            },
            {
                "title": "A Brief History of Time",
                "author": "Stephen Hawking",
                "isbn": "978-0553380163",
                "category": categories["Science"],
                "total_copies": 2,
                "available_copies": 1,
                "shelf_location": "SCI-01",
                "description": "Landmark volume explaining cosmology, the Big Bang, and black holes for all readers.",
            },
        ]

        created_books = []
        for b_dict in books_data:
            book, _ = Book.objects.get_or_create(
                isbn=b_dict["isbn"],
                defaults=b_dict
            )
            created_books.append(book)
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(created_books)} catalog books."))

        # 5. Create Sample Loans & Transactions
        today = timezone.now().date()

        # Loan 1: Active, On-time (Rahul borrowed Clean Code)
        BorrowRecord.objects.get_or_create(
            book=created_books[0],
            member=members[0],
            status=BorrowRecord.STATUS_ISSUED,
            defaults={
                "issued_by": librarian,
                "issue_date": today - timedelta(days=5),
                "due_date": today + timedelta(days=9),
            }
        )

        # Loan 2: Active, OVERDUE (Priya borrowed CLRS 20 days ago, due 6 days ago!)
        overdue_loan, ov_created = BorrowRecord.objects.get_or_create(
            book=created_books[1],
            member=members[1],
            status=BorrowRecord.STATUS_ISSUED,
            defaults={
                "issued_by": librarian,
                "issue_date": today - timedelta(days=20),
                "due_date": today - timedelta(days=6),  # 6 days overdue!
            }
        )
        if ov_created:
            self.stdout.write(self.style.WARNING("Created active overdue loan for testing overdue detection."))

        # Loan 3: Returned on time with 0 fine (Arjun borrowed and returned 1984)
        past_loan_1, _ = BorrowRecord.objects.get_or_create(
            book=created_books[4],
            member=members[2],
            status=BorrowRecord.STATUS_RETURNED,
            defaults={
                "issued_by": librarian,
                "issue_date": today - timedelta(days=30),
                "due_date": today - timedelta(days=16),
                "return_date": today - timedelta(days=18), # on time
            }
        )

        # Loan 4: Returned late with ₹15 fine (Rahul borrowed Design Patterns, returned 3 days late, unpaid fine)
        past_loan_2, pl2_created = BorrowRecord.objects.get_or_create(
            book=created_books[2],
            member=members[0],
            status=BorrowRecord.STATUS_RETURNED,
            defaults={
                "issued_by": librarian,
                "issue_date": today - timedelta(days=25),
                "due_date": today - timedelta(days=11),
                "return_date": today - timedelta(days=8), # 3 days late!
            }
        )
        if pl2_created:
            Fine.objects.create(
                borrow_record=past_loan_2,
                member=members[0],
                overdue_days=3,
                fine_rate=Decimal("5.00"),
                amount=Decimal("15.00"),
                is_paid=False,
            )
            self.stdout.write(self.style.SUCCESS("Created demo fine of ₹15.00 for Rahul (3 days late)."))

        # Loan 5: Returned late with paid fine (Priya paid ₹25 fine)
        past_loan_3, pl3_created = BorrowRecord.objects.get_or_create(
            book=created_books[6],
            member=members[1],
            status=BorrowRecord.STATUS_RETURNED,
            defaults={
                "issued_by": librarian,
                "issue_date": today - timedelta(days=40),
                "due_date": today - timedelta(days=26),
                "return_date": today - timedelta(days=21), # 5 days late
            }
        )
        if pl3_created:
            Fine.objects.create(
                borrow_record=past_loan_3,
                member=members[1],
                overdue_days=5,
                fine_rate=Decimal("5.00"),
                amount=Decimal("25.00"),
                is_paid=True,
                paid_date=timezone.now() - timedelta(days=15),
            )

        self.stdout.write(self.style.SUCCESS("Data seeding completed successfully!"))
