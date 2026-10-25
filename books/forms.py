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
            'book_value',
            'total_copies',
            'available_copies',
            'shelf_location',
            'description',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Book Title'}),
            'author': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Author Name'}),
            'isbn': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ISBN (e.g. 978-0132350884)'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'book_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Replacement Value in ₹'}),
            'total_copies': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'available_copies': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'shelf_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Shelf A-3'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Brief summary or notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['book_value'].required = False
        # For new book creation, default available_copies if not set
        if not self.instance.pk:
            self.fields['available_copies'].initial = 1
            self.fields['total_copies'].initial = 1
            self.fields['book_value'].initial = 500.00

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('book_value'):
            cleaned_data['book_value'] = 500.00
        total_copies = cleaned_data.get('total_copies')
        available_copies = cleaned_data.get('available_copies')

        if total_copies is not None and total_copies < 0:
            self.add_error('total_copies', "Total copies cannot be negative.")

        if available_copies is not None and available_copies < 0:
            self.add_error('available_copies', "Available copies cannot be negative.")

        if total_copies is not None and available_copies is not None:
            if available_copies > total_copies:
                self.add_error('available_copies', "Available copies cannot exceed total copies.")

            # If editing an existing book, check currently issued copies
            if self.instance.pk:
                currently_issued = self.instance.issued_copies
                if total_copies < currently_issued:
                    self.add_error(
                        'total_copies',
                        f"Cannot reduce total copies below currently issued count ({currently_issued})."
                    )

        return cleaned_data
