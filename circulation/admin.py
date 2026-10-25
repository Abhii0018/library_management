from django.contrib import admin
from .models import BorrowRecord, Fine, BorrowRequest


@admin.register(BorrowRequest)
class BorrowRequestAdmin(admin.ModelAdmin):
    list_display = ('member', 'book', 'requested_days', 'status', 'requested_at', 'reviewed_by', 'reviewed_at')
    list_filter = ('status', 'requested_at')
    search_fields = ('member__username', 'book__title', 'book__isbn')


@admin.register(BorrowRecord)
class BorrowRecordAdmin(admin.ModelAdmin):
    list_display = ('book', 'member', 'issue_date', 'due_date', 'return_date', 'status', 'issued_by')
    list_filter = ('status', 'issue_date', 'due_date', 'return_date')
    search_fields = ('book__title', 'book__isbn', 'member__username', 'member__email')


@admin.register(Fine)
class FineAdmin(admin.ModelAdmin):
    list_display = ('borrow_record', 'member', 'duration_days', 'overdue_days', 'amount', 'is_paid', 'paid_date')
    list_filter = ('is_paid', 'created_at')
    search_fields = ('member__username', 'borrow_record__book__title')

