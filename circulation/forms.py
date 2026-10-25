from datetime import timedelta
from django import forms
from django.utils import timezone
from accounts.models import User
from books.models import Book
from .models import BorrowRecord, Fine, BorrowRequest


class BorrowRequestForm(forms.Form):
    requested_days = forms.IntegerField(
        min_value=1,
        max_value=30,
        initial=5,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': 1,
            'max': 30,
            'placeholder': 'Enter duration in days (1 - 30)'
        }),
        label="Borrowing Duration (Days)",
        help_text="Specify how many days you need this book (between 1 and 30 days)."
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Optional remarks (e.g. course assignment, study purpose)'
        }),
        label="Notes / Purpose"
    )

    def clean_requested_days(self):
        days = self.cleaned_data.get('requested_days')
        if not days or days < 1:
            raise forms.ValidationError("Requested days must be at least 1 day.")
        if days > 30:
            raise forms.ValidationError("Requested borrowing duration cannot exceed 30 days.")
        return days


class IssueBookForm(forms.Form):
    member = forms.ModelChoiceField(
        queryset=User.objects.filter(role=User.ROLE_MEMBER).select_related('member_profile'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Select Member"
    )
    book = forms.ModelChoiceField(
        queryset=Book.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Select Book"
    )
    issue_date = forms.DateField(
        initial=timezone.now().date,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Issue Date"
    )
    requested_days = forms.IntegerField(
        initial=14,
        min_value=1,
        max_value=30,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 30}),
        label="Duration (Days)"
    )
    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Due Date",
        help_text="Automatically calculated from Issue Date + Duration."
    )
    request_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput()
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional remarks/condition of book'})
    )

    def __init__(self, *args, **kwargs):
        initial_member = kwargs.pop('initial_member', None)
        initial_book = kwargs.pop('initial_book', None)
        initial_request_id = kwargs.pop('initial_request_id', None)
        initial_requested_days = kwargs.pop('initial_requested_days', None)
        super().__init__(*args, **kwargs)

        today = timezone.now().date()
        req_days = initial_requested_days or 14

        if not self.is_bound:
            # On GET, populate select dropdown with only available books & active members
            self.fields['member'].queryset = User.objects.filter(
                role=User.ROLE_MEMBER,
                member_profile__is_blocked=False
            ).select_related('member_profile')
            self.fields['book'].queryset = Book.objects.filter(available_copies__gt=0)
            self.initial['requested_days'] = req_days
            self.initial['due_date'] = today + timedelta(days=req_days)
        else:
            # On POST, allow all so custom clean validations return specific descriptive errors
            self.fields['member'].queryset = User.objects.filter(role=User.ROLE_MEMBER).select_related('member_profile')
            self.fields['book'].queryset = Book.objects.all()

        if initial_member:
            self.fields['member'].initial = initial_member
        if initial_book:
            self.fields['book'].initial = initial_book
        if initial_request_id:
            self.fields['request_id'].initial = initial_request_id
        if initial_requested_days:
            self.fields['requested_days'].initial = initial_requested_days
            if not self.is_bound:
                self.fields['due_date'].initial = today + timedelta(days=initial_requested_days)

    def clean(self):
        cleaned_data = super().clean()
        member = cleaned_data.get('member')
        book = cleaned_data.get('book')
        issue_date = cleaned_data.get('issue_date')
        requested_days = cleaned_data.get('requested_days')
        due_date = cleaned_data.get('due_date')

        if not requested_days and issue_date and due_date:
            days = (due_date - issue_date).days
            requested_days = max(1, min(30, days))
            cleaned_data['requested_days'] = requested_days
        elif not requested_days:
            requested_days = 14
            cleaned_data['requested_days'] = requested_days

        if issue_date and not due_date:
            due_date = issue_date + timedelta(days=requested_days)
            cleaned_data['due_date'] = due_date

        if issue_date and due_date and due_date < issue_date:
            self.add_error('due_date', "Due date cannot be earlier than the issue date.")

        if member:
            profile = getattr(member, 'member_profile', None)
            if profile and profile.is_blocked:
                self.add_error('member', f"Member '{member.username}' is blocked. Cannot issue books to a blocked member.")

            active_borrows_count = BorrowRecord.objects.filter(
                member=member,
                status=BorrowRecord.STATUS_ISSUED
            ).count()
            
            if active_borrows_count >= 3:
                self.add_error(
                    'member',
                    "Maximum borrowing limit reached. You cannot borrow another book until one is returned."
                )

        if member and book:
            already_borrowed = BorrowRecord.objects.filter(
                member=member,
                book=book,
                status=BorrowRecord.STATUS_ISSUED
            ).exists()
            if already_borrowed:
                self.add_error(
                    'book',
                    f"Member already has an active copy of '{book.title}'."
                )

        if book and book.available_copies <= 0:
            self.add_error('book', f"Cannot issue '{book.title}'. No copies currently available.")

        return cleaned_data


class ReturnBookForm(forms.Form):
    return_date = forms.DateField(
        initial=timezone.now().date,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Return Date"
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Return notes (e.g. good condition)'})
    )

    def __init__(self, *args, borrow_record=None, **kwargs):
        self.borrow_record = borrow_record
        super().__init__(*args, **kwargs)

    def clean_return_date(self):
        return_date = self.cleaned_data.get('return_date')
        if self.borrow_record and return_date and return_date < self.borrow_record.issue_date:
            raise forms.ValidationError("Return date cannot be earlier than the issue date.")
        return return_date
