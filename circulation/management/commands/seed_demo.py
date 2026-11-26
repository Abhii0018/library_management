import os
import secrets
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import MemberProfile, StaffProfile, User
from books.models import Book
from circulation.models import BorrowRecord, BorrowRequest, Fine

DEMO_TAG = "[demo]"
STAFF_USERNAME = "demo_librarian"
MEMBER_SPECS = [
    ("demo_member1", "Aarav", "Mehta"),
    ("demo_member2", "Diya", "Kapoor"),
    ("demo_member3", "Kabir", "Singh"),
    ("demo_blocked", "Rohan", "Gill"),
]

# Each scenario uses its own book so no member holds two states for one title.
# days_ago values are relative to today. Fees are derived from the production
# fee function, never typed in.
PENDING_SCENARIOS = [
    {"key": "pending-1", "member": "demo_member1", "requested_days": 7},
    {"key": "pending-2", "member": "demo_member2", "requested_days": 14},
    {"key": "pending-3", "member": "demo_member3", "requested_days": 5},
]
ACTIVE_SCENARIOS = [
    {"key": "active-ontime", "member": "demo_member1", "requested_days": 14, "issued_days_ago": 5},
    {"key": "active-overdue", "member": "demo_member2", "requested_days": 14, "issued_days_ago": 20},
    {"key": "active-due-soon", "member": "demo_member3", "requested_days": 7, "issued_days_ago": 5},
]
RETURNED_SCENARIOS = [
    {"key": "returned-free", "member": "demo_member1", "requested_days": 7, "issued_days_ago": 6, "returned_days_ago": 5, "paid": True},
    {"key": "returned-fee-paid", "member": "demo_member2", "requested_days": 7, "issued_days_ago": 20, "returned_days_ago": 14, "paid": True},
    {"key": "returned-fee-unpaid", "member": "demo_member3", "requested_days": 3, "issued_days_ago": 12, "returned_days_ago": 8, "paid": False},
]


class Command(BaseCommand):
    help = (
        "Creates a small, internally consistent set of demo accounts, requests, loans "
        "and fees. Safe to re-run. Requires the catalogue (run seed_catalog first)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=os.environ.get("DEMO_PASSWORD"),
            help="Password for newly created demo accounts. Falls back to the DEMO_PASSWORD "
                 "environment variable, then to a random password printed once.",
        )

    def handle(self, *args, **options):
        password = options["password"]
        generated = False
        if not password:
            password = secrets.token_urlsafe(12)
            generated = True

        with transaction.atomic():
            staff, staff_created = self._ensure_staff(password)
            members, created_members = self._ensure_members(password)
            candidates = self._candidate_books()
            counts = {"requests": 0, "loans": 0, "returns": 0}
            book_iter = iter(candidates)
            for spec in PENDING_SCENARIOS:
                counts["requests"] += self._ensure_pending(spec, members, book_iter)
            for spec in ACTIVE_SCENARIOS:
                counts["loans"] += self._ensure_active(spec, members, staff, book_iter)
            for spec in RETURNED_SCENARIOS:
                counts["returns"] += self._ensure_returned(spec, members, staff, book_iter)

        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready. Created: {counts['requests']} pending requests, "
            f"{counts['loans']} active loans, {counts['returns']} completed returns."
        ))
        if staff_created or created_members:
            created_names = ([STAFF_USERNAME] if staff_created else []) + created_members
            self.stdout.write(f"New accounts: {', '.join(created_names)}")
            if generated:
                self.stdout.write(self.style.WARNING(
                    f"Generated password (shown once): {password}"
                ))
            else:
                self.stdout.write("Accounts use the password you supplied.")
        else:
            self.stdout.write("All demo accounts already existed; passwords were left unchanged.")

    def _ensure_staff(self, password):
        staff = User.objects.filter(username=STAFF_USERNAME).first()
        if staff:
            return staff, False
        staff = User(
            username=STAFF_USERNAME,
            first_name="Eleanor",
            last_name="Vance",
            email="demo.librarian@example.com",
            role=User.ROLE_STAFF,
            is_staff=True,
            is_superuser=False,
        )
        staff.set_password(password)
        staff.save()
        StaffProfile.objects.create(
            user=staff,
            staff_id=StaffProfile.generate_staff_id(),
            department="Circulation",
        )
        return staff, True

    def _ensure_members(self, password):
        members = {}
        created = []
        for username, first_name, last_name in MEMBER_SPECS:
            user = User.objects.filter(username=username).first()
            if user is None:
                user = User(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=f"{username}@example.com",
                    role=User.ROLE_MEMBER,
                )
                user.set_password(password)
                user.save()
                created.append(username)
            if not hasattr(user, "member_profile"):
                MemberProfile.objects.create(
                    user=user,
                    membership_id=MemberProfile.generate_membership_id(),
                    max_books_allowed=3,
                    is_blocked=(username == "demo_blocked"),
                )
            members[username] = user
        return members, created

    def _candidate_books(self):
        """Books with 2+ shelf copies whose counters match their active loans."""
        demo_book_ids = set(
            BorrowRecord.objects.filter(notes__startswith=DEMO_TAG).values_list("book_id", flat=True)
        ) | set(
            BorrowRequest.objects.filter(notes__startswith=DEMO_TAG).values_list("book_id", flat=True)
        )
        candidates = []
        for book in Book.objects.exclude(pk__in=demo_book_ids).order_by("pk"):
            if book.available_copies < 2:
                continue
            active = BorrowRecord.objects.filter(
                book=book, status=BorrowRecord.STATUS_ISSUED, return_date__isnull=True
            ).count()
            if book.available_copies == book.total_copies - active:
                candidates.append(book.pk)
        return candidates

    def _tag(self, key):
        return f"{DEMO_TAG}[{key}]"

    def _next_book(self, book_iter):
        try:
            book_pk = next(book_iter)
        except StopIteration:
            raise CommandError(
                "Not enough catalogue books with at least 2 consistent shelf copies. "
                "Run 'seed_catalog' first."
            )
        return Book.objects.select_for_update().get(pk=book_pk)

    def _ensure_pending(self, spec, members, book_iter):
        tag = self._tag(spec["key"])
        if BorrowRequest.objects.filter(notes=tag).exists():
            return 0
        BorrowRequest.objects.create(
            member=members[spec["member"]],
            book=self._next_book(book_iter),
            requested_days=spec["requested_days"],
            status=BorrowRequest.STATUS_PENDING,
            notes=tag,
        )
        return 1

    def _build_loan(self, spec, members, staff, book, returned):
        today = timezone.now().date()
        member = members[spec["member"]]
        issue_date = today - timedelta(days=spec["issued_days_ago"])
        reviewed_at = timezone.now() - timedelta(days=spec["issued_days_ago"])
        tag = self._tag(spec["key"])

        borrow_request = BorrowRequest.objects.create(
            member=member,
            book=book,
            requested_days=spec["requested_days"],
            status=BorrowRequest.STATUS_APPROVED,
            reviewed_by=staff,
            reviewed_at=reviewed_at,
            notes=tag,
        )
        record = BorrowRecord.objects.create(
            book=book,
            member=member,
            issued_by=staff,
            borrow_request=borrow_request,
            requested_days=spec["requested_days"],
            issue_date=issue_date,
            due_date=issue_date + timedelta(days=spec["requested_days"]),
            status=BorrowRecord.STATUS_ISSUED,
            notes=tag,
        )
        if not returned:
            book.available_copies -= 1
            book.save(update_fields=["available_copies"])
        return record

    def _ensure_active(self, spec, members, staff, book_iter):
        if BorrowRecord.objects.filter(notes=self._tag(spec["key"])).exists():
            return 0
        self._build_loan(spec, members, staff, self._next_book(book_iter), returned=False)
        return 1

    def _ensure_returned(self, spec, members, staff, book_iter):
        if BorrowRecord.objects.filter(notes=self._tag(spec["key"])).exists():
            return 0
        book = self._next_book(book_iter)
        record = self._build_loan(spec, members, staff, book, returned=True)

        record.return_date = timezone.now().date() - timedelta(days=spec["returned_days_ago"])
        record.status = BorrowRecord.STATUS_RETURNED
        record.save(update_fields=["return_date", "status", "updated_at"])

        duration = record.borrowing_duration()
        fee = BorrowRecord.calculate_borrowing_fee(duration)
        settled = fee == Decimal("0.00") or spec["paid"]
        Fine.objects.create(
            borrow_record=record,
            member=record.member,
            duration_days=duration,
            overdue_days=record.overdue_days(),
            amount=fee,
            is_paid=settled,
            paid_date=timezone.now() if settled else None,
        )
        return 1
