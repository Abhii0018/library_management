from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, MemberProfile, StaffProfile


class MemberProfileInline(admin.StackedInline):
    model = MemberProfile
    can_delete = False
    verbose_name_plural = 'Member Profile'


class StaffProfileInline(admin.StackedInline):
    model = StaffProfile
    can_delete = False
    verbose_name_plural = 'Staff Profile'


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = (MemberProfileInline, StaffProfileInline)
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Library Role', {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Library Role', {'fields': ('role',)}),
    )


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ('membership_id', 'user', 'phone', 'max_books_allowed', 'is_blocked', 'created_at')
    list_filter = ('is_blocked', 'max_books_allowed')
    search_fields = ('membership_id', 'user__username', 'user__email', 'phone')


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('staff_id', 'user', 'department', 'phone', 'created_at')
    search_fields = ('staff_id', 'user__username', 'user__email', 'department', 'phone')
