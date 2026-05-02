from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import Group
from .models import User

# Unregister the default Group admin
admin.site.unregister(Group)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'mobile_number', 'role', 'institute', 'is_staff')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role', 'institute', 'mobile_number')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Custom Fields', {'fields': ('role', 'institute', 'mobile_number')}),
    )

@admin.register(Group)
class CustomGroupAdmin(BaseGroupAdmin):
    """
    Enhanced Group Admin for better permission management.
    Uses filter_horizontal for a dual-list searchable interface.
    """
    filter_horizontal = ('permissions',)

    class Media:
        css = {
            'all': ('admin/css/custom_group_style.css',)
        }
        js = ('admin/js/custom_group_js.js',)
