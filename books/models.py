from django.db import models
from django.core.exceptions import ValidationError


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="Genre or Category Name")
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=255, db_index=True)
    author = models.CharField(max_length=255, db_index=True)
    isbn = models.CharField(max_length=20, unique=True, db_index=True, help_text="10 or 13 digit ISBN")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='books'
    )
    total_copies = models.PositiveIntegerField(
        default=1,
        help_text="Total number of physical copies possessed."
    )
    available_copies = models.PositiveIntegerField(
        default=1,
        help_text="Copies currently on the shelf and available for borrowing."
    )
    shelf_location = models.CharField(
        max_length=50,
        blank=True,
        help_text="e.g. Section B, Shelf 3"
    )
    book_value = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=500.00,
        help_text="Book Value / Replacement cost in ₹ (not the borrowing fee)"
    )
    description = models.TextField(blank=True)
    added_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f"{self.title} by {self.author} (ISBN: {self.isbn})"

    def clean(self):
        super().clean()
        if self.available_copies is not None and self.available_copies < 0:
            raise ValidationError({
                'available_copies': "Available copies cannot be negative."
            })
        if self.total_copies is not None and self.total_copies < 0:
            raise ValidationError({
                'total_copies': "Total copies cannot be negative."
            })
        if self.available_copies is not None and self.total_copies is not None and self.available_copies > self.total_copies:
            raise ValidationError({
                'available_copies': "Available copies cannot exceed total copies."
            })

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def issued_copies(self):
        return max(0, self.total_copies - self.available_copies)

    @property
    def is_available(self):
        return self.available_copies > 0
