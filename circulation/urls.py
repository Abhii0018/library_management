from django.urls import path
from . import views

app_name = 'circulation'

urlpatterns = [
    # Borrow requests
    path('requests/', views.borrow_request_list_view, name='request_list'),
    path('requests/<int:book_id>/create/', views.create_borrow_request_view, name='create_request'),
    path('requests/<int:pk>/approve/', views.approve_borrow_request_view, name='approve_request'),
    path('requests/<int:pk>/reject/', views.reject_borrow_request_view, name='reject_request'),

    # Admin Dedicated Pages: Currently Borrowed & History
    path('borrowed/', views.admin_currently_borrowed_view, name='admin_borrowed'),
    path('history/', views.admin_borrowing_history_view, name='admin_history'),

    # Member Dedicated Pages: Currently Borrowed, History & Requests
    path('my-borrowed/', views.member_currently_borrowed_view, name='member_borrowed'),
    path('my-history/', views.member_borrowing_history_view, name='member_history'),
    path('my-requests/', views.member_borrow_requests_view, name='member_requests'),

    # Issue and return
    path('issue/', views.issue_book_view, name='issue_book'),
    path('return/', views.return_book_select_view, name='return_book_select'),
    path('return/<int:pk>/', views.return_book_view, name='return_book'),

    # Transactions & Fees
    path('transactions/', views.transaction_list_view, name='transaction_list'),
    path('fines/', views.fine_list_view, name='fine_list'),
    path('fines/<int:pk>/pay/', views.mark_fine_paid_view, name='mark_fine_paid'),
]
