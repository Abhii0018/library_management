from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index_view, name='index'),
    path('welcome/', views.landing_page_view, name='landing'),
    path('dashboard/admin/', views.admin_dashboard_view, name='admin_dashboard'),
    path('dashboard/staff/', views.staff_dashboard_view, name='staff_dashboard'),
    path('dashboard/librarian/', views.librarian_dashboard_view, name='librarian_dashboard'),
    path('dashboard/member/', views.member_dashboard_view, name='member_dashboard'),
]
