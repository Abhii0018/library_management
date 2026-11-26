from django import forms
from .models import Book, Category


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Computer Science'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional description'}),
        }


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = [
            'title',
            'author',
            'isbn',
            'category',
            'publisher',
            'publication_year',
            'edition',
            'language',
            'page_count',
            'book_value',
            'total_copies',
            'shelf_location',
            'cover_image',
            'description',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Book Title'}),
            'author': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Author Name'}),
            'isbn': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ISBN (e.g. 978-0132350884)'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'publisher': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. MIT Press'}),
            'publication_year': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2021'}),
            'edition': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 3rd Edition'}),
            'language': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. English'}),
            'page_count': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 450'}),
            'book_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Replacement Value in ₹'}),
            'total_copies': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'shelf_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Shelf A-3'}),
            'cover_image': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. images/covers/9780132350884.jpg'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Brief summary or notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['book_value'].required = False
        self.fields['total_copies'].help_text = "Available copies are derived automatically from active loans."
        if not self.instance.pk:
            self.fields['total_copies'].initial = 1
            self.fields['book_value'].initial = 500.00

    def _active_loan_count(self):
        if not self.instance.pk:
            return 0
        return self.instance.borrow_records.filter(status='ISSUED', return_date__isnull=True).count()

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('book_value'):
            cleaned_data['book_value'] = 500.00

        total_copies = cleaned_data.get('total_copies')
        if total_copies is not None:
            if total_copies < 1:
                self.add_error('total_copies', "Total copies must be at least 1.")
            active_loans = self._active_loan_count()
            if total_copies < active_loans:
                self.add_error(
                    'total_copies',
                    f"Cannot reduce total copies below the {active_loans} currently on loan."
                )
        return cleaned_data

    def save(self, commit=True):
        book = super().save(commit=False)
        book.available_copies = book.total_copies - self._active_loan_count()
        if commit:
            book.save()
        return book
