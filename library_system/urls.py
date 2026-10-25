"""
URL configuration for library_system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from accounts import views as account_views
from circulation import views as circulation_views

urlpatterns = [
    # Admin dedicated borrowing pages
    path('admin/borrowed/', circulation_views.admin_currently_borrowed_view, name='root_admin_borrowed'),
    path('admin/history/', circulation_views.admin_borrowing_history_view, name='root_admin_history'),

    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('accounts/', include('accounts.urls')),
    path('books/', include('books.urls')),
    path('circulation/', include('circulation.urls')),

    # Member dedicated borrowing pages
    path('borrowed/', circulation_views.member_currently_borrowed_view, name='root_member_borrowed'),
    path('history/', circulation_views.member_borrowing_history_view, name='root_member_history'),
    path('requests/', circulation_views.member_borrow_requests_view, name='root_member_requests'),

    # Additional routes for direct path access & strict authorization checks
    path('transactions/', circulation_views.transaction_list_view, name='root_transaction_list'),
    path('transactions/requests/', circulation_views.borrow_request_list_view, name='root_request_list'),
    path('transactions/requests/<int:pk>/approve/', circulation_views.approve_borrow_request_view, name='root_approve_request'),
    path('transactions/requests/<int:pk>/reject/', circulation_views.reject_borrow_request_view, name='root_reject_request'),
    path('transactions/issue/', circulation_views.issue_book_view, name='root_issue_book'),
    path('transactions/return/', circulation_views.return_book_select_view, name='root_return_book_select'),
    path('transactions/return/<int:pk>/', circulation_views.return_book_view, name='root_return_book'),
    path('transactions/fines/', circulation_views.fine_list_view, name='root_fine_list'),
    path('transactions/fines/<int:pk>/pay/', circulation_views.mark_fine_paid_view, name='root_mark_fine_paid'),

    path('members/', account_views.member_list_view, name='root_member_list'),
    path('members/add/', account_views.member_create_view, name='root_member_create'),
    path('members/<int:pk>/', account_views.member_detail_view, name='root_member_detail'),
    path('members/<int:pk>/edit/', account_views.member_edit_view, name='root_member_edit'),
    path('members/<int:pk>/toggle-block/', account_views.member_toggle_block_view, name='root_member_toggle_block'),

    # Staff routes
    path('staff/', account_views.staff_list_view, name='root_staff_list'),
    path('staff/create/', account_views.staff_create_view, name='root_staff_create'),
    path('staff/<int:pk>/edit/', account_views.staff_edit_view, name='root_staff_edit'),
    path('staff/<int:pk>/toggle-status/', account_views.staff_toggle_status_view, name='root_staff_toggle_status'),
]
