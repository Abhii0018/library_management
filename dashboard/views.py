from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.utils import timezone
from accounts.models import User, MemberProfile, StaffProfile
from books.models import Book, Category
from circulation.models import BorrowRecord, Fine, BorrowRequest
from accounts.decorators import librarian_required, admin_required, staff_or_admin_required


def landing_page_view(request):
    """
    Public landing page for the LibriCore Library Management System.
    """
    total_books = Book.objects.count()
    total_copies = Book.objects.aggregate(total=Sum('total_copies'))['total'] or 0
    total_available_copies = Book.objects.aggregate(total=Sum('available_copies'))['total'] or 0
    total_members = User.objects.filter(role=User.ROLE_MEMBER).count()
    total_categories = Category.objects.count()
    categories = Category.objects.all()[:8]
    featured_books = Book.objects.select_related('category').order_by('-added_date')[:6]

    context = {
        'total_books': total_books,
        'total_copies': total_copies,
        'total_available_copies': total_available_copies,
        'total_members': total_members,
        'total_categories': total_categories,
        'categories': categories,
        'featured_books': featured_books,
    }
    return render(request, 'landing.html', context)


def index_view(request):
    """
    Root view: redirects authenticated users to their respective role dashboard,
    and shows the standard public landing page to guests.
    """
    if request.user.is_authenticated:
        user = request.user
        if user.role == User.ROLE_ADMIN or (user.is_superuser and user.role != User.ROLE_STAFF):
            return redirect('dashboard:admin_dashboard')
        elif user.role == User.ROLE_STAFF:
            return redirect('dashboard:staff_dashboard')
        elif user.role == User.ROLE_LIBRARIAN:
            return redirect('dashboard:librarian_dashboard')
        return redirect('dashboard:member_dashboard')
    return landing_page_view(request)


def _get_management_dashboard_context(request, dashboard_type='librarian'):
    today = timezone.now().date()

    # Books Statistics
    total_books = Book.objects.count()
    total_copies = Book.objects.aggregate(total=Sum('total_copies'))['total'] or 0
    total_available_copies = Book.objects.aggregate(total=Sum('available_copies'))['total'] or 0
    total_issued_copies = BorrowRecord.objects.filter(status=BorrowRecord.STATUS_ISSUED).count()

    # Members Statistics
    total_members = User.objects.filter(role=User.ROLE_MEMBER).count()
    active_members = User.objects.filter(role=User.ROLE_MEMBER, member_profile__is_blocked=False).count()
    blocked_members = User.objects.filter(role=User.ROLE_MEMBER, member_profile__is_blocked=True).count()

    # Staff Statistics (for Admin)
    total_staff = User.objects.filter(role__in=[User.ROLE_STAFF, User.ROLE_LIBRARIAN]).count()

    # Requests Statistics
    pending_requests_count = BorrowRequest.objects.filter(status=BorrowRequest.STATUS_PENDING).count()
    approved_requests_count = BorrowRequest.objects.filter(status=BorrowRequest.STATUS_APPROVED).count()

    # Loans Statistics
    issued_books_count = total_issued_copies
    returned_books_count = BorrowRecord.objects.filter(status=BorrowRecord.STATUS_RETURNED).count()
    overdue_records = BorrowRecord.objects.filter(
        status=BorrowRecord.STATUS_ISSUED,
        due_date__lt=today
    )
    overdue_books_count = overdue_records.count()

    # Fees Statistics
    pending_fines_sum = Fine.objects.filter(is_paid=False).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    paid_fines_sum = Fine.objects.filter(is_paid=True).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Recent Data
    recent_requests = BorrowRequest.objects.select_related('book', 'member', 'member__member_profile').order_by('-requested_at')[:6]
    recent_transactions = BorrowRecord.objects.select_related('book', 'member').order_by('-created_at')[:8]
    urgent_overdues = overdue_records.select_related('book', 'member')[:6]

    if dashboard_type == 'admin':
        page_title = 'Admin Dashboard'
        page_subtitle = 'System administration, staff management, catalog inventory, and circulation oversight'
    elif dashboard_type == 'staff':
        page_title = 'Staff Dashboard'
        page_subtitle = 'Live catalog inventory, member records, borrow requests, and circulation activity'
    else:
        page_title = 'Librarian Dashboard'
        page_subtitle = 'Live inventory metrics, borrow requests, circulation activity, and pending alerts'

    return {
        'dashboard_type': dashboard_type,
        'page_title_custom': page_title,
        'page_subtitle_custom': page_subtitle,
        'total_books': total_books,
        'total_copies': total_copies,
        'total_available_copies': total_available_copies,
        'total_issued_copies': total_issued_copies,
        'total_members': total_members,
        'active_members': active_members,
        'blocked_members': blocked_members,
        'total_staff': total_staff,
        'pending_requests_count': pending_requests_count,
        'approved_requests_count': approved_requests_count,
        'issued_books_count': issued_books_count,
        'returned_books_count': returned_books_count,
        'overdue_books_count': overdue_books_count,
        'pending_fines_sum': pending_fines_sum,
        'paid_fines_sum': paid_fines_sum,
        'recent_requests': recent_requests,
        'recent_transactions': recent_transactions,
        'urgent_overdues': urgent_overdues,
        'today': today,
    }


@admin_required
def admin_dashboard_view(request):
    context = _get_management_dashboard_context(request, dashboard_type='admin')
    return render(request, 'dashboard/librarian_dashboard.html', context)


@staff_or_admin_required
def staff_dashboard_view(request):
    context = _get_management_dashboard_context(request, dashboard_type='staff')
    return render(request, 'dashboard/librarian_dashboard.html', context)


@librarian_required
def librarian_dashboard_view(request):
    context = _get_management_dashboard_context(request, dashboard_type='librarian')
    return render(request, 'dashboard/librarian_dashboard.html', context)


@login_required
def member_dashboard_view(request):
    today = timezone.now().date()
    user = request.user

    profile = getattr(user, 'member_profile', None)

    # Member's active loans
    current_borrows = BorrowRecord.objects.filter(
        member=user,
        status=BorrowRecord.STATUS_ISSUED
    ).select_related('book').order_by('due_date')

    # Member's borrow requests
    my_requests = BorrowRequest.objects.filter(
        member=user
    ).select_related('book').order_by('-requested_at')

    # Member's loan history
    borrow_history = BorrowRecord.objects.filter(
        member=user,
        status=BorrowRecord.STATUS_RETURNED
    ).select_related('book', 'fine').order_by('-return_date')[:15]

    # Member's fines / fees
    member_fines = Fine.objects.filter(member=user).select_related('borrow_record', 'borrow_record__book')
    pending_fines = member_fines.filter(is_paid=False)
    pending_fine_sum = pending_fines.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    overdue_count = sum(1 for b in current_borrows if b.due_date < today)
    pending_requests_count = my_requests.filter(status=BorrowRequest.STATUS_PENDING).count()

    context = {
        'profile': profile,
        'current_borrows': current_borrows,
        'my_requests': my_requests,
        'pending_requests_count': pending_requests_count,
        'borrow_history': borrow_history,
        'pending_fines': pending_fines,
        'pending_fine_sum': pending_fine_sum,
        'overdue_count': overdue_count,
        'today': today,
    }
    return render(request, 'dashboard/member_dashboard.html', context)
