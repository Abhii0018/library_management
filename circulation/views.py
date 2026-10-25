from decimal import Decimal
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, F, Sum
from django.utils import timezone
from django.conf import settings
from .models import BorrowRecord, Fine, BorrowRequest
from .forms import IssueBookForm, ReturnBookForm, BorrowRequestForm
from books.models import Book
from accounts.models import User
from accounts.decorators import librarian_required


# ==========================================
# BORROW REQUESTS (Member & Admin)
# ==========================================

@login_required
def create_borrow_request_view(request, book_id):
    """
    Member requests to borrow a book for a specified number of days (1 to 30).
    """
    if request.user.is_librarian:
        messages.info(request, "Librarians can issue books directly without submitting a borrow request.")
        return redirect('books:book_detail', pk=book_id)

    book = get_object_or_404(Book, pk=book_id)
    profile = getattr(request.user, 'member_profile', None)

    # 1. Member Status validation: Blocked members cannot request books
    if profile and profile.is_blocked:
        messages.error(request, "Your account is currently blocked. You cannot submit new borrowing requests.")
        return redirect('books:book_detail', pk=book_id)

    # 2. Maximum Borrowing Limit: Max 3 active borrowed books
    active_loans = BorrowRecord.objects.filter(
        member=request.user,
        status=BorrowRecord.STATUS_ISSUED
    ).count()
    if active_loans >= 3:
        messages.error(
            request,
            "Maximum borrowing limit reached. Return a book before requesting another."
        )
        return redirect('books:book_detail', pk=book_id)

    # 3. Duplicate Request Prevention: No multiple pending/approved requests for same book
    existing_request = BorrowRequest.objects.filter(
        member=request.user,
        book=book,
        status__in=[BorrowRequest.STATUS_PENDING, BorrowRequest.STATUS_APPROVED]
    ).first()
    if existing_request:
        if existing_request.status == BorrowRequest.STATUS_PENDING:
            messages.warning(request, f"You already have a pending request for '{book.title}'. Please wait for Librarian review.")
        else:
            messages.info(request, f"Your request for '{book.title}' is approved! Please visit the library counter to borrow it.")
        return redirect('books:book_detail', pk=book_id)

    # 4. Check if member already has an active issued copy of this book
    already_has_book = BorrowRecord.objects.filter(
        member=request.user,
        book=book,
        status=BorrowRecord.STATUS_ISSUED
    ).exists()
    if already_has_book:
        messages.warning(request, f"You currently have a borrowed copy of '{book.title}'.")
        return redirect('books:book_detail', pk=book_id)

    # 5. Book availability check
    if book.available_copies <= 0:
        messages.error(request, f"'{book.title}' currently has no copies available to request.")
        return redirect('books:book_detail', pk=book_id)

    if request.method == 'POST':
        form = BorrowRequestForm(request.POST)
        if form.is_valid():
            requested_days = form.cleaned_data['requested_days']
            notes = form.cleaned_data['notes']

            # Create request with PENDING status (does NOT decrease copies)
            borrow_req = BorrowRequest.objects.create(
                member=request.user,
                book=book,
                requested_days=requested_days,
                status=BorrowRequest.STATUS_PENDING,
                notes=notes
            )
            messages.success(
                request,
                f"Borrow request for '{book.title}' ({requested_days} days) submitted successfully! Status: Pending Librarian review."
            )
            return redirect('dashboard:member_dashboard')
        else:
            for error in form.errors.values():
                messages.error(request, error[0])
            return redirect('books:book_detail', pk=book_id)

    return redirect('books:book_detail', pk=book_id)


@librarian_required
def borrow_request_list_view(request):
    """
    Admin/Librarian view of all borrow requests from all members.
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    requests_qs = BorrowRequest.objects.select_related('member', 'member__member_profile', 'book', 'reviewed_by').all()

    if query:
        requests_qs = requests_qs.filter(
            Q(book__title__icontains=query) |
            Q(book__isbn__icontains=query) |
            Q(member__username__icontains=query) |
            Q(member__first_name__icontains=query) |
            Q(member__last_name__icontains=query) |
            Q(member__member_profile__membership_id__icontains=query)
        )

    if status_filter:
        requests_qs = requests_qs.filter(status=status_filter.upper())

    total_requests = BorrowRequest.objects.count()
    pending_count = BorrowRequest.objects.filter(status=BorrowRequest.STATUS_PENDING).count()
    approved_count = BorrowRequest.objects.filter(status=BorrowRequest.STATUS_APPROVED).count()

    context = {
        'requests': requests_qs,
        'query': query,
        'status_filter': status_filter,
        'total_requests': total_requests,
        'pending_count': pending_count,
        'approved_count': approved_count,
    }
    return render(request, 'circulation/request_list.html', context)


@librarian_required
def approve_borrow_request_view(request, pk):
    """
    Admin/Staff accepts a pending borrow request.
    The approval itself IS the issue/borrow action (no secondary issue step).
    Immediately creates BorrowRecord, sets issue date to current date,
    calculates due date from requested_days, decreases available copies by 1,
    and updates request status to APPROVED.
    """
    if request.method == 'POST':
        with transaction.atomic():
            borrow_req = get_object_or_404(
                BorrowRequest.objects.select_for_update().select_related('book', 'member'),
                pk=pk
            )

            # 1. Validate request is still Pending
            if borrow_req.status != BorrowRequest.STATUS_PENDING:
                messages.info(request, f"This request is already marked as {borrow_req.get_status_display()}.")
                return redirect('circulation:request_list')

            # 2. Validate member is active
            profile = getattr(borrow_req.member, 'member_profile', None)
            if profile and profile.is_blocked:
                messages.error(request, f"Cannot approve: Member '{borrow_req.member.username}' is currently blocked.")
                return redirect('circulation:request_list')

            # 3. Validate active loans limit (< 3)
            active_loans = BorrowRecord.objects.filter(
                member=borrow_req.member,
                status=BorrowRecord.STATUS_ISSUED
            ).count()
            if active_loans >= 3:
                messages.error(
                    request,
                    f"Cannot approve: Member '{borrow_req.member.username}' already has 3 active borrowed books. Maximum limit reached."
                )
                return redirect('circulation:request_list')

            # 4. Validate requested duration (1 to 30 days)
            if not borrow_req.requested_days or borrow_req.requested_days < 1 or borrow_req.requested_days > 30:
                messages.error(request, "Cannot approve: Invalid requested duration. Must be between 1 and 30 days.")
                return redirect('circulation:request_list')

            # 5. Lock book and validate availability
            book_obj = Book.objects.select_for_update().get(pk=borrow_req.book.pk)
            if book_obj.available_copies <= 0:
                messages.error(request, "Book is no longer available.")
                return redirect('circulation:request_list')

            # 6. Prevent duplicate active loan for the same book
            if BorrowRecord.objects.filter(member=borrow_req.member, book=book_obj, status=BorrowRecord.STATUS_ISSUED).exists():
                messages.error(request, f"Member '{borrow_req.member.username}' already has an active copy of '{book_obj.title}'.")
                return redirect('circulation:request_list')

            # 7. Dates calculation
            issue_date = timezone.now().date()
            due_date = issue_date + timedelta(days=borrow_req.requested_days)

            # 8. Create borrowing transaction record immediately
            BorrowRecord.objects.create(
                book=book_obj,
                member=borrow_req.member,
                issued_by=request.user,
                borrow_request=borrow_req,
                requested_days=borrow_req.requested_days,
                issue_date=issue_date,
                due_date=due_date,
                status=BorrowRecord.STATUS_ISSUED,
                notes=borrow_req.notes or f"Issued on request approval (#{borrow_req.pk})"
            )

            # 9. Decrease available copies by EXACTLY 1
            book_obj.available_copies = book_obj.available_copies - 1
            book_obj.save(update_fields=['available_copies'])

            # 10. Update request status to APPROVED
            borrow_req.status = BorrowRequest.STATUS_APPROVED
            borrow_req.reviewed_by = request.user
            borrow_req.reviewed_at = timezone.now()
            borrow_req.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])

        messages.success(
            request,
            f"Request accepted! Book '{book_obj.title}' has been immediately issued to {borrow_req.member.get_full_name() or borrow_req.member.username}. Due on {due_date} ({borrow_req.requested_days} days)."
        )
        return redirect('circulation:request_list')

    return redirect('circulation:request_list')


@librarian_required
def reject_borrow_request_view(request, pk):
    """
    Admin rejects a pending borrow request.
    """
    if request.method == 'POST':
        borrow_req = get_object_or_404(BorrowRequest, pk=pk)
        if borrow_req.status != BorrowRequest.STATUS_PENDING:
            messages.info(request, f"This request is already marked as {borrow_req.get_status_display()}.")
            return redirect('circulation:request_list')

        borrow_req.status = BorrowRequest.STATUS_REJECTED
        borrow_req.reviewed_by = request.user
        borrow_req.reviewed_at = timezone.now()
        borrow_req.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])

        messages.warning(request, f"Request #{borrow_req.pk} for '{borrow_req.book.title}' has been rejected.")
        return redirect('circulation:request_list')

    return redirect('circulation:request_list')


# ==========================================
# ISSUE & RETURN WORKFLOWS
# ==========================================

@librarian_required
def issue_book_view(request):
    initial_member = request.GET.get('member_id')
    initial_book = request.GET.get('book_id')
    request_id = request.GET.get('request_id')

    initial_requested_days = 14
    borrow_req = None

    if request_id:
        try:
            borrow_req = BorrowRequest.objects.select_related('member', 'book').get(pk=request_id)
            initial_member = borrow_req.member.pk
            initial_book = borrow_req.book.pk
            initial_requested_days = borrow_req.requested_days
        except BorrowRequest.DoesNotExist:
            pass

    if request.method == 'POST':
        form = IssueBookForm(request.POST)
        if form.is_valid():
            member = form.cleaned_data['member']
            book = form.cleaned_data['book']
            issue_date = form.cleaned_data['issue_date']
            requested_days = form.cleaned_data.get('requested_days') or 14
            due_date = form.cleaned_data.get('due_date') or (issue_date + timedelta(days=requested_days))
            notes = form.cleaned_data.get('notes', '')
            req_id_submitted = form.cleaned_data.get('request_id')

            # 1. Member existence & role
            if not member or member.role != User.ROLE_MEMBER:
                messages.error(request, "Selected user is not an eligible library member.")
                return render(request, 'circulation/issue_book.html', {'form': form})

            # 2. Member status: Blocked check
            profile = getattr(member, 'member_profile', None)
            if profile and profile.is_blocked:
                messages.error(request, f"Member '{member.username}' is blocked. Cannot issue books to a blocked member.")
                return render(request, 'circulation/issue_book.html', {'form': form})

            # 3. Maximum borrowing limit: 3 active loans
            active_loans = BorrowRecord.objects.filter(
                member=member,
                status=BorrowRecord.STATUS_ISSUED
            ).count()
            if active_loans >= 3:
                messages.error(
                    request,
                    "Maximum borrowing limit reached. You cannot borrow another book until one is returned."
                )
                return render(request, 'circulation/issue_book.html', {'form': form})

            # 4. Duplicate active loan check
            if BorrowRecord.objects.filter(member=member, book=book, status=BorrowRecord.STATUS_ISSUED).exists():
                messages.error(request, f"Member '{member.username}' already has an active copy of '{book.title}'.")
                return render(request, 'circulation/issue_book.html', {'form': form})

            # 5. Due date check
            if due_date < issue_date:
                messages.error(request, "Due date cannot be earlier than the issue date.")
                return render(request, 'circulation/issue_book.html', {'form': form})

            with transaction.atomic():
                # 6. Book availability check & row lock
                book_obj = Book.objects.select_for_update().get(pk=book.pk)
                if book_obj.available_copies <= 0:
                    messages.error(request, f"Cannot issue '{book_obj.title}'. No copies currently available.")
                    return render(request, 'circulation/issue_book.html', {'form': form})

                # Check linked request
                req_obj = None
                if req_id_submitted:
                    try:
                        req_obj = BorrowRequest.objects.select_for_update().get(pk=req_id_submitted)
                    except BorrowRequest.DoesNotExist:
                        req_obj = None
                elif borrow_req:
                    req_obj = borrow_req

                # Create the transaction
                borrow_record = BorrowRecord.objects.create(
                    book=book_obj,
                    member=member,
                    issued_by=request.user,
                    borrow_request=req_obj,
                    requested_days=requested_days,
                    issue_date=issue_date,
                    due_date=due_date,
                    status=BorrowRecord.STATUS_ISSUED,
                    notes=notes,
                )

                # Officially decrease available copies by 1
                book_obj.available_copies = book_obj.available_copies - 1
                book_obj.save(update_fields=['available_copies'])

                # Mark request as Completed / Issued
                if req_obj:
                    req_obj.status = BorrowRequest.STATUS_COMPLETED
                    req_obj.reviewed_by = req_obj.reviewed_by or request.user
                    req_obj.reviewed_at = req_obj.reviewed_at or timezone.now()
                    req_obj.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])

            messages.success(
                request,
                f"Book '{book.title}' was successfully issued to {member.get_full_name() or member.username}. Duration: {requested_days} days (Due on {due_date})."
            )
            return redirect('circulation:transaction_list')
        else:
            messages.error(request, "Please resolve the errors below to issue the book.")
    else:
        form = IssueBookForm(
            initial_member=initial_member,
            initial_book=initial_book,
            initial_request_id=request_id,
            initial_requested_days=initial_requested_days
        )

    return render(request, 'circulation/issue_book.html', {
        'form': form,
        'borrow_req': borrow_req
    })


@librarian_required
def return_book_view(request, pk):
    borrow_record = get_object_or_404(
        BorrowRecord.objects.select_related('book', 'member', 'member__member_profile'),
        pk=pk
    )

    if borrow_record.status == BorrowRecord.STATUS_RETURNED or borrow_record.return_date is not None:
        messages.warning(
            request,
            f"This transaction (Loan #{borrow_record.pk}) has already been returned. Cannot return again."
        )
        return redirect('circulation:transaction_list')

    # Calculate preview borrowing duration & fee
    today = timezone.now().date()
    preview_duration = borrow_record.borrowing_duration(as_of_date=today)
    preview_fee = BorrowRecord.calculate_borrowing_fee(preview_duration)
    overdue_days_preview = borrow_record.overdue_days(target_date=today)

    if request.method == 'POST':
        form = ReturnBookForm(request.POST, borrow_record=borrow_record)
        if form.is_valid():
            return_date = form.cleaned_data['return_date']
            notes = form.cleaned_data.get('notes', '')

            with transaction.atomic():
                # Re-verify and lock record
                record_to_update = BorrowRecord.objects.select_for_update().get(pk=pk)
                if record_to_update.status == BorrowRecord.STATUS_RETURNED or record_to_update.return_date is not None:
                    messages.warning(request, "This transaction has already been returned. Cannot return again.")
                    return redirect('circulation:transaction_list')

                book = Book.objects.select_for_update().get(pk=record_to_update.book.pk)
                
                # Calculate actual borrowing duration and fee (Section 16 Policy):
                actual_duration = record_to_update.borrowing_duration(as_of_date=return_date)
                calculated_fee = BorrowRecord.calculate_borrowing_fee(actual_duration)
                overdue_days = record_to_update.overdue_days(target_date=return_date)

                record_to_update.return_date = return_date
                record_to_update.status = BorrowRecord.STATUS_RETURNED
                if notes:
                    record_to_update.notes = (record_to_update.notes + f"\nReturn note: {notes}").strip()
                record_to_update.save(update_fields=['return_date', 'status', 'notes', 'updated_at'])

                # Officially increase available copies by 1 (capped at total_copies)
                if book.available_copies < book.total_copies:
                    book.available_copies = book.available_copies + 1
                    book.save(update_fields=['available_copies'])

                # Record borrowing fee in Fine model
                fee_record, _ = Fine.objects.update_or_create(
                    borrow_record=record_to_update,
                    defaults={
                        'member': record_to_update.member,
                        'duration_days': actual_duration,
                        'overdue_days': overdue_days,
                        'amount': calculated_fee,
                        'is_paid': (calculated_fee == Decimal('0.00')),
                        'paid_date': timezone.now() if calculated_fee == Decimal('0.00') else None,
                    }
                )

            if calculated_fee > Decimal('0.00'):
                messages.warning(
                    request,
                    f"Book '{borrow_record.book.title}' returned. Total duration: {actual_duration} days. Borrowing fee due: ₹{calculated_fee}."
                )
            else:
                messages.success(
                    request,
                    f"Book '{borrow_record.book.title}' returned successfully. Borrowing duration: {actual_duration} days. Free borrowing period applied (Fee: ₹0)."
                )

            return redirect('circulation:admin_borrowed')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ReturnBookForm(borrow_record=borrow_record)

    context = {
        'borrow_record': borrow_record,
        'form': form,
        'preview_duration': preview_duration,
        'preview_fee': preview_fee,
        'overdue_days_preview': overdue_days_preview,
    }
    return render(request, 'circulation/return_book.html', context)


@librarian_required
def return_book_select_view(request):
    messages.info(request, "Please select an active loan from the transaction list to process its return.")
    return redirect('circulation:transaction_list')


@librarian_required
def transaction_list_view(request):
    """
    Admin views all transactions from all members with complete details.
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    today = timezone.now().date()
    records = BorrowRecord.objects.select_related('book', 'member', 'issued_by', 'fine', 'member__member_profile')

    if query:
        records = records.filter(
            Q(book__title__icontains=query) |
            Q(book__isbn__icontains=query) |
            Q(member__username__icontains=query) |
            Q(member__first_name__icontains=query) |
            Q(member__last_name__icontains=query) |
            Q(member__member_profile__membership_id__icontains=query)
        )

    if status_filter == 'issued':
        records = records.filter(status=BorrowRecord.STATUS_ISSUED, due_date__gte=today)
    elif status_filter == 'overdue':
        records = records.filter(status=BorrowRecord.STATUS_ISSUED, due_date__lt=today)
    elif status_filter == 'returned':
        records = records.filter(status=BorrowRecord.STATUS_RETURNED)

    records = records.order_by('-created_at')

    context = {
        'records': records,
        'query': query,
        'status_filter': status_filter,
        'today': today,
    }
    return render(request, 'circulation/transaction_list.html', context)


@librarian_required
def fine_list_view(request):
    """
    Admin views all borrowing fees from all members.
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    fines = Fine.objects.select_related('member', 'borrow_record', 'borrow_record__book', 'member__member_profile')

    if query:
        fines = fines.filter(
            Q(member__username__icontains=query) |
            Q(member__first_name__icontains=query) |
            Q(member__last_name__icontains=query) |
            Q(member__member_profile__membership_id__icontains=query) |
            Q(borrow_record__book__title__icontains=query)
        )

    if status_filter == 'pending':
        fines = fines.filter(is_paid=False)
    elif status_filter == 'paid':
        fines = fines.filter(is_paid=True)

    total_pending = Fine.objects.filter(is_paid=False).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_paid = Fine.objects.filter(is_paid=True).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    context = {
        'fines': fines,
        'query': query,
        'status_filter': status_filter,
        'total_pending': total_pending,
        'total_paid': total_paid,
    }
    return render(request, 'circulation/fine_list.html', context)


@librarian_required
def mark_fine_paid_view(request, pk):
    if request.method == 'POST':
        fine = get_object_or_404(Fine, pk=pk)
        if not fine.is_paid:
            fine.is_paid = True
            fine.paid_date = timezone.now()
            fine.save(update_fields=['is_paid', 'paid_date', 'updated_at'])
            messages.success(request, f"Borrowing fee of ₹{fine.amount} for {fine.member.username} marked as SETTLED / PAID.")
        else:
            messages.info(request, "This fee is already marked as paid.")
        return redirect('circulation:fine_list')
    return redirect('circulation:fine_list')


# ==========================================
# DEDICATED PAGES: CURRENTLY BORROWED & HISTORY
# ==========================================

@login_required
def member_currently_borrowed_view(request):
    """
    Dedicated Member page for currently active borrowings (/borrowed/).
    Shows only books that the logged-in member currently has.
    """
    if request.user.is_librarian:
        return redirect('circulation:admin_borrowed')

    user = request.user
    active_borrows = BorrowRecord.objects.filter(
        member=user,
        status=BorrowRecord.STATUS_ISSUED,
        return_date__isnull=True
    ).select_related('book').order_by('due_date')

    profile = getattr(user, 'member_profile', None)
    max_allowed = profile.max_books_allowed if profile else 3
    today = timezone.now().date()

    context = {
        'active_borrows': active_borrows,
        'count': active_borrows.count(),
        'max_allowed': max_allowed,
        'today': today,
    }
    return render(request, 'circulation/member_currently_borrowed.html', context)


@login_required
def member_borrowing_history_view(request):
    """
    Dedicated Member page for completed borrowing history (/history/).
    Shows only completed/returned transactions for the logged-in member.
    """
    if request.user.is_librarian:
        return redirect('circulation:admin_history')

    user = request.user
    history_records = BorrowRecord.objects.filter(
        member=user,
        status=BorrowRecord.STATUS_RETURNED,
        return_date__isnull=False
    ).select_related('book', 'fine').order_by('-return_date', '-issue_date')

    context = {
        'history_records': history_records,
    }
    return render(request, 'circulation/member_borrowing_history.html', context)


@login_required
def member_borrow_requests_view(request):
    """
    Dedicated Member page for viewing own borrow requests (/requests/).
    """
    if request.user.is_librarian:
        return redirect('circulation:request_list')

    user = request.user
    my_requests = BorrowRequest.objects.filter(
        member=user
    ).select_related('book').order_by('-requested_at')

    context = {
        'my_requests': my_requests,
    }
    return render(request, 'circulation/member_borrow_requests.html', context)


@librarian_required
def admin_currently_borrowed_view(request):
    """
    Dedicated Admin page for all currently active borrowings across all members (/admin/borrowed/).
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    today = timezone.now().date()

    records = BorrowRecord.objects.filter(
        status=BorrowRecord.STATUS_ISSUED,
        return_date__isnull=True
    ).select_related('book', 'member', 'member__member_profile', 'issued_by')

    if query:
        records = records.filter(
            Q(book__title__icontains=query) |
            Q(book__isbn__icontains=query) |
            Q(member__username__icontains=query) |
            Q(member__first_name__icontains=query) |
            Q(member__last_name__icontains=query) |
            Q(member__member_profile__membership_id__icontains=query)
        )

    if status_filter == 'overdue':
        records = records.filter(due_date__lt=today)
    elif status_filter == 'active':
        records = records.filter(due_date__gte=today)

    records = records.order_by('due_date')

    total_active = BorrowRecord.objects.filter(status=BorrowRecord.STATUS_ISSUED, return_date__isnull=True).count()
    overdue_count = BorrowRecord.objects.filter(status=BorrowRecord.STATUS_ISSUED, return_date__isnull=True, due_date__lt=today).count()

    context = {
        'records': records,
        'query': query,
        'status_filter': status_filter,
        'total_active': total_active,
        'overdue_count': overdue_count,
        'today': today,
    }
    return render(request, 'circulation/admin_currently_borrowed.html', context)


@librarian_required
def admin_borrowing_history_view(request):
    """
    Dedicated Admin page for all completed borrowing transactions across all members (/admin/history/).
    """
    query = request.GET.get('q', '').strip()

    records = BorrowRecord.objects.filter(
        status=BorrowRecord.STATUS_RETURNED,
        return_date__isnull=False
    ).select_related('book', 'member', 'member__member_profile', 'issued_by', 'fine')

    if query:
        records = records.filter(
            Q(book__title__icontains=query) |
            Q(book__isbn__icontains=query) |
            Q(member__username__icontains=query) |
            Q(member__first_name__icontains=query) |
            Q(member__last_name__icontains=query) |
            Q(member__member_profile__membership_id__icontains=query)
        )

    records = records.order_by('-return_date', '-issue_date')

    total_returned = BorrowRecord.objects.filter(status=BorrowRecord.STATUS_RETURNED, return_date__isnull=False).count()
    total_fines_collected = Fine.objects.filter(is_paid=True).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    context = {
        'records': records,
        'query': query,
        'total_returned': total_returned,
        'total_fines_collected': total_fines_collected,
    }
    return render(request, 'circulation/admin_borrowing_history.html', context)
