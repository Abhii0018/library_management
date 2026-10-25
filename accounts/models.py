import random
from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_ADMIN = 'ADMIN'
    ROLE_STAFF = 'STAFF'
    ROLE_LIBRARIAN = 'LIBRARIAN'  # Backward compatibility alias
    ROLE_MEMBER = 'MEMBER'

    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Administrator'),
        (ROLE_STAFF, 'Staff Member'),
        (ROLE_LIBRARIAN, 'Librarian / Staff'),
        (ROLE_MEMBER, 'Member / Student'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_MEMBER,
        db_index=True,
        help_text="Designates the user role in the library system."
    )

    @property
    def is_admin_user(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser

    @property
    def is_staff_user(self):
        return self.role in [self.ROLE_STAFF, self.ROLE_LIBRARIAN] or (self.is_staff and not self.is_superuser)

    @property
    def is_librarian(self):
        """
        Returns True for any user authorized to manage circulation & library books (Admin and Staff).
        Preserves backward compatibility across existing views/tests.
        """
        return self.is_admin_user or self.is_staff_user or self.is_staff or self.is_superuser

    @property
    def is_member(self):
        return self.role == self.ROLE_MEMBER

    def __str__(self):
        full_name = self.get_full_name()
        display = full_name if full_name else self.username
        return f"{display} ({self.get_role_display()})"


class MemberProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='member_profile'
    )
    membership_id = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        help_text="Unique Member ID (e.g. MEM-1001)"
    )
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    max_books_allowed = models.PositiveSmallIntegerField(
        default=3,
        help_text="Maximum number of simultaneous books this member can borrow."
    )
    is_blocked = models.BooleanField(
        default=False,
        help_text="If blocked, member cannot be issued new books."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.membership_id} - {self.user.get_full_name() or self.user.username}"

    @classmethod
    def generate_membership_id(cls):
        while True:
            candidate = f"MEM-{random.randint(10000, 99999)}"
            if not cls.objects.filter(membership_id=candidate).exists():
                return candidate


class StaffProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='staff_profile'
    )
    staff_id = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        help_text="Unique Staff ID (e.g. STF-1001)"
    )
    phone = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=100, blank=True, default="Circulation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.staff_id} - {self.user.get_full_name() or self.user.username}"

    @classmethod
    def generate_staff_id(cls):
        while True:
            candidate = f"STF-{random.randint(1000, 9999)}"
            if not cls.objects.filter(staff_id=candidate).exists():
                return candidate
