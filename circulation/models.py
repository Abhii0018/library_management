from decimal import Decimal
from datetime import timedelta
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from accounts.models import User
from books.models import Book


class BorrowRequest(models.Model):
    STATUS_PENDING = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_COMPLETED = 'COMPLETED'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_COMPLETED, 'Completed / Issued'),
    ]

    member = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='borrow_requests',
        limit_choices_to={'role': User.ROLE_MEMBER}
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='borrow_requests'
    )
    requested_days = models.PositiveIntegerField(
        help_text="Requested borrowing duration in days (1 to 30)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_requests'
    )
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"Request by {self.member.username} for {self.book.title} ({self.status})"

    def clean(self):
        super().clean()
        if self.requested_days is not None:
            if self.requested_days < 1:
                raise ValidationError({'requested_days': "Requested days must be at least 1."})
            if self.requested_days > 30:
                raise ValidationError({'requested_days': "Requested days cannot exceed 30 days."})


class BorrowRecord(models.Model):
    STATUS_ISSUED = 'ISSUED'
    STATUS_RETURNED = 'RETURNED'
    STATUS_OVERDUE = 'OVERDUE'

    STATUS_CHOICES = [
        (STATUS_ISSUED, 'Issued'),
        (STATUS_RETURNED, 'Returned'),
        (STATUS_OVERDUE, 'Overdue'),
    ]

    book = models.ForeignKey(
        Book,
        on_delete=models.PROTECT,
        related_name='borrow_records'
    )
    member = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='borrowed_records',
        limit_choices_to={'role': User.ROLE_MEMBER}
    )
    issued_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_by_records',
        help_text="Librarian who approved the issuance"
    )
    borrow_request = models.ForeignKey(
        BorrowRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='borrow_records'
    )
    requested_days = models.PositiveIntegerField(
        default=14,
        help_text="Requested/approved borrowing duration in days"
    )
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ISSUED,
        db_index=True
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-issue_date', '-created_at']

    def __str__(self):
        return f"{self.book.title} issued to {self.member.username} ({self.status})"

    def clean(self):
        super().clean()
        if self.due_date and self.issue_date and self.due_date < self.issue_date:
            raise ValidationError({
                'due_date': "Due date cannot be earlier than issue date."
            })
        if self.return_date and self.issue_date and self.return_date < self.issue_date:
            raise ValidationError({
                'return_date': "Return date cannot be earlier than issue date."
            })

    def borrowing_duration(self, as_of_date=None):
        """
        Calculate actual borrowing duration in days.
        If returned, difference between return_date and issue_date.
        If active, difference between today (or as_of_date) and issue_date.
        Same day counts as 1 day minimum.
        """
        end_date = self.return_date if self.return_date else (as_of_date or timezone.now().date())
        if self.issue_date and end_date >= self.issue_date:
            days = (end_date - self.issue_date).days
            return max(1, days)
        return 1

    def overdue_days(self, target_date=None):
        """
        Calculate overdue days past due_date.
        """
        ref_date = self.return_date if self.return_date else (target_date or timezone.now().date())
        if self.due_date and ref_date > self.due_date:
            return (ref_date - self.due_date).days
        return 0

    @property
    def is_currently_overdue(self):
        if self.status == self.STATUS_RETURNED:
            return False
        return self.due_date < timezone.now().date()

    @classmethod
    def calculate_borrowing_fee(cls, days):
        """
        Borrowing Fee Policy (Section 16):
        First 2 days: FREE (₹0)
        Day 3 onward: ₹20 per day
        If borrowing duration exceeds 5 days: Add one-time ₹100 penalty

        Examples:
        1 day = ₹0
        2 days = ₹0
        3 days = ₹20
        4 days = ₹40
        5 days = ₹60
        6 days = ₹160
        7 days = ₹180
        """
        if days <= 2:
            return Decimal('0.00')
        elif days <= 5:
            return Decimal((days - 2) * 20)
        else:
            return Decimal(160 + (days - 6) * 20)

    @property
    def current_fee(self):
        """Returns fee for active or returned borrow record"""
        days = self.borrowing_duration()
        return self.calculate_borrowing_fee(days)


class Fine(models.Model):
    borrow_record = models.OneToOneField(
        BorrowRecord,
        on_delete=models.CASCADE,
        related_name='fine'
    )
    member = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='fines'
    )
    duration_days = models.PositiveIntegerField(default=0, help_text="Total borrowing duration in days")
    overdue_days = models.PositiveIntegerField(default=0)
    fine_rate = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('20.00'),
        help_text="Standard daily borrowing fee rate"
    )
    amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Calculated total borrowing fee / fine"
    )
    is_paid = models.BooleanField(default=False, db_index=True)
    paid_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status = "PAID" if self.is_paid else "PENDING"
        return f"Fee: ₹{self.amount} for {self.member.username} ({status})"
