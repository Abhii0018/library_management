from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def admin_required(view_func):
    """
    Decorator for views that strictly checks that the user is logged in and is an Administrator.
    Staff and Members are denied access.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not getattr(request.user, 'is_admin_user', False):
            messages.error(request, "Access denied. Only Administrators can access this section.")
            if getattr(request.user, 'is_staff_user', False):
                return redirect('dashboard:staff_dashboard')
            return redirect('dashboard:member_dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def staff_or_admin_required(view_func):
    """
    Decorator for views that checks that the user is logged in and is either Admin or Staff.
    Members are denied access.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_librarian:
            messages.error(request, "Access denied. Only Staff and Administrators can access this section.")
            return redirect('dashboard:member_dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# Backward compatibility alias
librarian_required = staff_or_admin_required


def member_required(view_func):
    """
    Decorator for views that checks that the user is logged in.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
