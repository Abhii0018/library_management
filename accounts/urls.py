from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_view, name='profile'),
    path('password-change/', views.password_change_view, name='password_change'),
    
    # Member management (Librarian/Staff/Admin)
    path('members/', views.member_list_view, name='member_list'),
    path('members/add/', views.member_create_view, name='member_create'),
    path('members/<int:pk>/', views.member_detail_view, name='member_detail'),
    path('members/<int:pk>/edit/', views.member_edit_view, name='member_edit'),
    path('members/<int:pk>/toggle-block/', views.member_toggle_block_view, name='member_toggle_block'),

    # Staff management (Admin only)
    path('staff/', views.staff_list_view, name='staff_list'),
    path('staff/create/', views.staff_create_view, name='staff_create'),
    path('staff/<int:pk>/edit/', views.staff_edit_view, name='staff_edit'),
    path('staff/<int:pk>/toggle-status/', views.staff_toggle_status_view, name='staff_toggle_status'),
]
