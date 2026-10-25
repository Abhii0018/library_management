from django.urls import path
from . import views

app_name = 'books'

urlpatterns = [
    path('', views.book_list_view, name='book_list'),
    path('add/', views.book_create_view, name='book_create'),
    path('delete/', views.book_delete_root_view, name='book_delete_root'),
    path('<int:pk>/', views.book_detail_view, name='book_detail'),
    path('<int:pk>/edit/', views.book_edit_view, name='book_edit'),
    path('<int:pk>/delete/', views.book_delete_view, name='book_delete'),
]
