from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from simple_history.admin import SimpleHistoryAdmin

from apps.users.models import User


@admin.register(User)
class UserAdmin(SimpleHistoryAdmin, DjangoUserAdmin):
    model = User
    list_display = ('email', 'name', 'role', 'is_landlord', 'is_staff', 'is_active', 'created_at')
    list_filter = ('role', 'is_landlord', 'is_staff', 'is_active')
    search_fields = ('email', 'name')
    ordering = ('-created_at',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('name', 'role', 'is_landlord')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'role', 'password1', 'password2'),
        }),
    )