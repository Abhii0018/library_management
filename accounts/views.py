from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from .models import User, MemberProfile, StaffProfile
from .forms import (
    UserLoginForm,
    MemberRegistrationForm,
    LibrarianMemberCreateForm,
    MemberEditForm,
    UserProfileForm,
    CustomPasswordChangeForm,
    StaffCreateForm,
    StaffEditForm,
)
from .decorators import librarian_required, admin_required, staff_or_admin_required


def get_user_dashboard_redirect(user):
    if user.role == User.ROLE_ADMIN or (user.is_superuser and user.role != User.ROLE_STAFF):
        return redirect('dashboard:admin_dashboard')
    elif user.role == User.ROLE_STAFF:
        return redirect('dashboard:staff_dashboard')
    elif user.role == User.ROLE_LIBRARIAN:
        return redirect('dashboard:librarian_dashboard')
    return redirect('dashboard:member_dashboard')


def login_view(request):
    if request.user.is_authenticated:
        return get_user_dashboard_redirect(request.user)

    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return get_user_dashboard_redirect(user)
        else:
            username_candidate = request.POST.get('username')
            user_candidate = User.objects.filter(username=username_candidate).first()
            if user_candidate and not user_candidate.is_active:
                messages.error(request, "This account is deactivated. Please contact the administrator.")
            else:
                messages.error(request, "Invalid username or password.")
    else:
        form = UserLoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('accounts:login')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    if request.method == 'POST':
        form = MemberRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Account created successfully for {user.username}! Please log in.")
            return redirect('accounts:login')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = MemberRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect('accounts:profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def password_change_view(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your password was successfully updated!")
            return redirect('accounts:profile')
        else:
            messages.error(request, "Please correct the error below.")
    else:
        form = CustomPasswordChangeForm(user=request.user)

    return render(request, 'accounts/password_change.html', {'form': form})


@librarian_required
def member_list_view(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    members = User.objects.filter(role=User.ROLE_MEMBER).select_related('member_profile')

    if query:
        members = members.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(member_profile__membership_id__icontains=query) |
            Q(member_profile__phone__icontains=query)
        )

    if status_filter == 'blocked':
        members = members.filter(member_profile__is_blocked=True)
    elif status_filter == 'active':
        members = members.filter(member_profile__is_blocked=False)

    members = members.order_by('-member_profile__created_at')

    context = {
        'members': members,
        'query': query,
        'status_filter': status_filter,
    }
    return render(request, 'accounts/member_list.html', context)


@librarian_required
def member_create_view(request):
    if request.method == 'POST':
        form = LibrarianMemberCreateForm(request.POST)
        if form.is_valid():
            member = form.save()
            messages.success(
                request,
                f"Member '{member.get_full_name() or member.username}' registered with ID {member.member_profile.membership_id}."
            )
            return redirect('accounts:member_detail', pk=member.pk)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = LibrarianMemberCreateForm()

    return render(request, 'accounts/member_form.html', {'form': form, 'title': 'Register New Member'})


@librarian_required
def member_detail_view(request, pk):
    member = get_object_or_404(User.objects.select_related('member_profile'), pk=pk, role=User.ROLE_MEMBER)
    borrow_records = member.borrowed_records.select_related('book', 'fine').order_by('-issue_date')
    active_borrows = borrow_records.filter(status='ISSUED')
    borrow_requests = member.borrow_requests.select_related('book').order_by('-requested_at')
    
    total_fines = member.fines.all()
    pending_fine_sum = total_fines.filter(is_paid=False).aggregate(total=Sum('amount'))['total'] or 0
    paid_fine_sum = total_fines.filter(is_paid=True).aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'member': member,
        'profile': getattr(member, 'member_profile', None),
        'borrow_records': borrow_records,
        'active_borrows': active_borrows,
        'borrow_requests': borrow_requests,
        'pending_fine_sum': pending_fine_sum,
        'paid_fine_sum': paid_fine_sum,
    }
    return render(request, 'accounts/member_detail.html', context)


@librarian_required
def member_edit_view(request, pk):
    member = get_object_or_404(User.objects.select_related('member_profile'), pk=pk, role=User.ROLE_MEMBER)

    if request.method == 'POST':
        form = MemberEditForm(request.POST, instance=member)
        if form.is_valid():
            form.save()
            messages.success(request, f"Member details for {member.username} updated successfully.")
            return redirect('accounts:member_detail', pk=member.pk)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = MemberEditForm(instance=member)

    return render(request, 'accounts/member_form.html', {'form': form, 'title': f'Edit Member: {member.username}', 'member': member})


@librarian_required
def member_toggle_block_view(request, pk):
    if request.method == 'POST':
        member = get_object_or_404(User, pk=pk, role=User.ROLE_MEMBER)
        profile = member.member_profile
        profile.is_blocked = not profile.is_blocked
        profile.save()
        status_text = "blocked" if profile.is_blocked else "unblocked"
        messages.success(request, f"Member {member.username} has been {status_text}.")
        return redirect('accounts:member_detail', pk=member.pk)
    return redirect('accounts:member_list')


# ==========================================
# STAFF MANAGEMENT (ADMIN-ONLY)
# ==========================================

@admin_required
def staff_list_view(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    staff_members = User.objects.filter(
        role__in=[User.ROLE_STAFF, User.ROLE_LIBRARIAN]
    ).select_related('staff_profile')

    if query:
        staff_members = staff_members.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(staff_profile__staff_id__icontains=query) |
            Q(staff_profile__phone__icontains=query) |
            Q(staff_profile__department__icontains=query)
        )

    if status_filter == 'active':
        staff_members = staff_members.filter(is_active=True)
    elif status_filter == 'inactive':
        staff_members = staff_members.filter(is_active=False)

    staff_members = staff_members.order_by('-date_joined')

    context = {
        'staff_members': staff_members,
        'query': query,
        'status_filter': status_filter,
    }
    return render(request, 'accounts/staff_list.html', context)


@admin_required
def staff_create_view(request):
    if request.method == 'POST':
        form = StaffCreateForm(request.POST)
        if form.is_valid():
            staff = form.save()
            staff_id = getattr(getattr(staff, 'staff_profile', None), 'staff_id', 'Assigned')
            messages.success(
                request,
                f"Staff account for '{staff.get_full_name() or staff.username}' created successfully with Staff ID {staff_id}."
            )
            return redirect('accounts:staff_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = StaffCreateForm(initial={'staff_id': StaffProfile.generate_staff_id()})

    return render(request, 'accounts/staff_form.html', {
        'form': form,
        'title': 'Create New Staff Member',
        'is_edit': False,
    })


@admin_required
def staff_edit_view(request, pk):
    staff = get_object_or_404(
        User.objects.select_related('staff_profile'),
        pk=pk,
        role__in=[User.ROLE_STAFF, User.ROLE_LIBRARIAN]
    )

    if request.method == 'POST':
        form = StaffEditForm(request.POST, instance=staff)
        if form.is_valid():
            form.save()
            messages.success(request, f"Staff account '{staff.username}' updated successfully.")
            return redirect('accounts:staff_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = StaffEditForm(instance=staff)

    return render(request, 'accounts/staff_form.html', {
        'form': form,
        'title': f'Edit Staff Member: {staff.username}',
        'staff_member': staff,
        'is_edit': True,
    })


@admin_required
def staff_toggle_status_view(request, pk):
    if request.method == 'POST':
        staff = get_object_or_404(
            User,
            pk=pk,
            role__in=[User.ROLE_STAFF, User.ROLE_LIBRARIAN]
        )
        staff.is_active = not staff.is_active
        staff.save()
        status_text = "activated" if staff.is_active else "deactivated"
        messages.success(request, f"Staff account '{staff.username}' has been {status_text}.")
        return redirect('accounts:staff_list')
    return redirect('accounts:staff_list')
