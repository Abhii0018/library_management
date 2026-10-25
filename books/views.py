from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Book, Category
from .forms import BookForm, CategoryForm
from accounts.decorators import librarian_required


@login_required
def book_list_view(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()
    availability = request.GET.get('availability', '').strip()

    books = Book.objects.select_related('category').all()

    if query:
        books = books.filter(
            Q(title__icontains=query) |
            Q(author__icontains=query) |
            Q(isbn__icontains=query)
        )

    if category_id:
        books = books.filter(category_id=category_id)

    if availability == 'available':
        books = books.filter(available_copies__gt=0)
    elif availability == 'unavailable':
        books = books.filter(available_copies=0)

    categories = Category.objects.all()

    context = {
        'books': books,
        'categories': categories,
        'query': query,
        'selected_category': category_id,
        'selected_availability': availability,
    }
    return render(request, 'books/book_list.html', context)


@login_required
def book_detail_view(request, pk):
    book = get_object_or_404(Book.objects.select_related('category'), pk=pk)
    
    # If librarian, also show current active loans and recent borrow history for this book
    active_borrows = []
    past_borrows = []
    user_request = None
    user_active_loan = False
    at_borrow_limit = False
    is_blocked = False
    request_form = None

    if request.user.is_librarian:
        active_borrows = book.borrow_records.filter(status='ISSUED').select_related('member')
        past_borrows = book.borrow_records.filter(status='RETURNED').select_related('member')[:10]
    else:
        from circulation.forms import BorrowRequestForm
        from circulation.models import BorrowRequest, BorrowRecord

        profile = getattr(request.user, 'member_profile', None)
        is_blocked = bool(profile and profile.is_blocked)

        active_loans_count = BorrowRecord.objects.filter(
            member=request.user,
            status=BorrowRecord.STATUS_ISSUED
        ).count()
        at_borrow_limit = (active_loans_count >= 3)

        user_active_loan = BorrowRecord.objects.filter(
            member=request.user,
            book=book,
            status=BorrowRecord.STATUS_ISSUED
        ).exists()

        # Get latest active or pending request
        user_request = BorrowRequest.objects.filter(
            member=request.user,
            book=book
        ).order_by('-requested_at').first()

        request_form = BorrowRequestForm()

    context = {
        'book': book,
        'active_borrows': active_borrows,
        'past_borrows': past_borrows,
        'user_request': user_request,
        'user_active_loan': user_active_loan,
        'at_borrow_limit': at_borrow_limit,
        'is_blocked': is_blocked,
        'request_form': request_form,
    }
    return render(request, 'books/book_detail.html', context)



@librarian_required
def book_create_view(request):
    if request.method == 'POST':
        form = BookForm(request.POST)
        if form.is_valid():
            book = form.save()
            messages.success(request, f"Book '{book.title}' added successfully!")
            return redirect('books:book_detail', pk=book.pk)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = BookForm()

    return render(request, 'books/book_form.html', {'form': form, 'title': 'Add New Book'})


@librarian_required
def book_edit_view(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        form = BookForm(request.POST, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, f"Book '{book.title}' updated successfully!")
            return redirect('books:book_detail', pk=book.pk)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = BookForm(instance=book)

    return render(request, 'books/book_form.html', {'form': form, 'title': f'Edit Book: {book.title}', 'book': book})


@librarian_required
def book_delete_view(request, pk):
    book = get_object_or_404(Book, pk=pk)

    # Business rule: Cannot delete book if any copies are currently issued out
    active_loans = book.borrow_records.filter(status='ISSUED').count()
    if active_loans > 0:
        messages.error(
            request,
            f"Cannot delete '{book.title}'. There are currently {active_loans} copy/copies issued to members."
        )
        return redirect('books:book_detail', pk=book.pk)

    if request.method == 'POST':
        title = book.title
        book.delete()
        messages.success(request, f"Book '{title}' was deleted successfully.")
        return redirect('books:book_list')

    return render(request, 'books/book_confirm_delete.html', {'book': book})


@librarian_required
def book_delete_root_view(request):
    messages.info(request, "Please select a book from the catalog to delete.")
    return redirect('books:book_list')

