from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from urllib.parse import urlencode
from django.db import IntegrityError, transaction
from django.db.models import Q, Value
from django.db.models.functions import Replace
from django.db.models.deletion import ProtectedError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpRequest, HttpResponse
from .models import Book, Category
from .forms import BookForm, CategoryForm
from accounts.decorators import librarian_required


@login_required
def book_list_view(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()
    availability = request.GET.get('availability', '').strip()
    sort_by = request.GET.get('sort', 'title').strip()

    books_qs = Book.objects.select_related('category').annotate(
        isbn_plain=Replace('isbn', Value('-'), Value(''))
    )

    if query:
        compact_query = query.replace('-', '').replace(' ', '')
        books_qs = books_qs.filter(
            Q(title__icontains=query) |
            Q(author__icontains=query) |
            Q(isbn__icontains=query) |
            Q(isbn_plain__icontains=compact_query)
        )

    if category_id.isdigit():
        books_qs = books_qs.filter(category_id=int(category_id))
    else:
        category_id = ''

    if availability == 'available':
        books_qs = books_qs.filter(available_copies__gt=0)
    elif availability == 'unavailable':
        books_qs = books_qs.filter(available_copies=0)

    sort_orderings = {
        'newest': ('-added_date', 'title', 'pk'),
        'author': ('author', 'title', 'pk'),
        'year': ('-publication_year', 'title', 'pk'),
        'title': ('title', 'pk'),
    }
    if sort_by not in sort_orderings:
        sort_by = 'title'
    books_qs = books_qs.order_by(*sort_orderings[sort_by])

    paginator = Paginator(books_qs, 15)
    page = request.GET.get('page', 1)
    try:
        books = paginator.page(page)
    except PageNotAnInteger:
        books = paginator.page(1)
    except EmptyPage:
        books = paginator.page(paginator.num_pages)

    categories = Category.objects.all()

    filter_params = {
        key: value for key, value in (
            ('q', query),
            ('category', category_id),
            ('availability', availability),
            ('sort', sort_by if sort_by != 'title' else ''),
        ) if value
    }

    context = {
        'filter_querystring': urlencode(filter_params),
        'books': books,
        'page_obj': books,
        'paginator': paginator,
        'total_count': paginator.count,
        'categories': categories,
        'query': query,
        'selected_category': category_id,
        'selected_availability': availability,
        'sort_by': sort_by,
    }
    return render(request, 'books/book_list.html', context)


def _handle_reservation_post(request: HttpRequest, pk: int) -> HttpResponse:
    from circulation.models import BookReservation, BorrowRecord

    if request.user.is_librarian:
        messages.info(request, "Librarians do not place holds. Members reserve titles for themselves.")
        return redirect('books:book_detail', pk=pk)

    action = request.POST.get('action')
    with transaction.atomic():
        # Locking the book serialises reserve/return so a hold is never placed on a copy
        # that a concurrent return has just put back on the shelf.
        book = get_object_or_404(Book.objects.select_for_update(), pk=pk)

        if action == 'reserve':
            profile = getattr(request.user, 'member_profile', None)
            if profile is not None and profile.is_blocked:
                messages.error(request, "Your reader clearance is suspended. Inquire at the circulation counter.")
            elif book.available_copies > 0:
                messages.info(request, "Copies are on the shelf. Submit a borrow request instead of a hold.")
            elif BorrowRecord.objects.filter(
                member=request.user, book=book,
                status=BorrowRecord.STATUS_ISSUED, return_date__isnull=True,
            ).exists():
                messages.info(request, "You already hold an active loan of this title.")
            elif BookReservation.objects.filter(
                member=request.user, book=book, status=BookReservation.STATUS_PENDING
            ).exists():
                messages.warning(request, "You are already on the waitlist for this title.")
            else:
                try:
                    with transaction.atomic():
                        BookReservation.objects.create(book=book, member=request.user)
                except IntegrityError:
                    messages.warning(request, "You are already on the waitlist for this title.")
                else:
                    messages.success(
                        request,
                        f"Hold placed on '{book.title}'. Staff will be alerted when a copy is returned."
                    )
        elif action == 'cancel':
            cancelled = BookReservation.objects.filter(
                member=request.user, book=book, status=BookReservation.STATUS_PENDING
            ).update(status=BookReservation.STATUS_CANCELLED)
            if cancelled:
                messages.success(request, f"Your hold on '{book.title}' was cancelled.")
            else:
                messages.info(request, "You have no pending hold on this title.")
        else:
            messages.error(request, "Unrecognised action.")
    return redirect('books:book_detail', pk=pk)


@login_required
def book_detail_view(request, pk):
    if request.method == 'POST':
        return _handle_reservation_post(request, pk)

    book = get_object_or_404(Book.objects.select_related('category'), pk=pk)
    
    # If librarian, also show current active loans and recent borrow history for this book
    active_borrows = []
    past_borrows = []
    user_request = None
    user_active_loan = False
    at_borrow_limit = False
    is_blocked = False
    request_form = None
    borrow_limit = None
    user_reservation = None
    queue_position = None
    fulfilled_hold = None
    waitlist_count = 0

    if request.user.is_librarian:
        active_borrows = book.borrow_records.filter(status='ISSUED').select_related('member')
        past_borrows = book.borrow_records.filter(status='RETURNED').select_related('member')[:10]
    else:
        from circulation.forms import BorrowRequestForm
        from circulation.models import BorrowRequest, BorrowRecord

        profile = getattr(request.user, 'member_profile', None)
        is_blocked = bool(profile and profile.is_blocked)

        from circulation.models import is_at_borrow_limit, member_borrow_limit
        at_borrow_limit = is_at_borrow_limit(request.user)
        borrow_limit = member_borrow_limit(request.user)

        user_active_loan = BorrowRecord.objects.filter(
            member=request.user,
            book=book,
            status=BorrowRecord.STATUS_ISSUED
        ).exists()

        # Get latest active or pending request
        user_request = BorrowRequest.objects.filter(
            member=request.user,
            book=book,
            status=BorrowRequest.STATUS_PENDING
        ).order_by('-requested_at').first()

        request_form = BorrowRequestForm()

        from circulation.models import BookReservation
        pending_holds = BookReservation.objects.filter(book=book, status=BookReservation.STATUS_PENDING)
        waitlist_count = pending_holds.count()
        user_reservation = pending_holds.filter(member=request.user).first()
        if user_reservation:
            queue_position = pending_holds.filter(
                Q(created_at__lt=user_reservation.created_at)
                | Q(created_at=user_reservation.created_at, pk__lt=user_reservation.pk)
            ).count() + 1
        else:
            latest_fulfilled = BookReservation.objects.filter(
                book=book, member=request.user, status=BookReservation.STATUS_FULFILLED
            ).order_by('-created_at').first()
            if latest_fulfilled and not user_active_loan and not BorrowRecord.objects.filter(
                member=request.user, book=book, created_at__gte=latest_fulfilled.created_at
            ).exists():
                fulfilled_hold = latest_fulfilled

    context = {
        'user_reservation': user_reservation,
        'queue_position': queue_position,
        'fulfilled_hold': fulfilled_hold,
        'waitlist_count': waitlist_count,
        'book': book,
        'active_borrows': active_borrows,
        'past_borrows': past_borrows,
        'user_request': user_request,
        'user_active_loan': user_active_loan,
        'at_borrow_limit': at_borrow_limit,
        'borrow_limit': borrow_limit,
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
        try:
            book.delete()
        except ProtectedError:
            messages.error(
                request,
                f"Cannot delete '{title}'. It has borrowing history that must be preserved."
            )
            return redirect('books:book_detail', pk=book.pk)
        messages.success(request, f"Book '{title}' was deleted successfully.")
        return redirect('books:book_list')

    return render(request, 'books/book_confirm_delete.html', {'book': book})


@librarian_required
def book_delete_root_view(request):
    messages.info(request, "Please select a book from the catalog to delete.")
    return redirect('books:book_list')

