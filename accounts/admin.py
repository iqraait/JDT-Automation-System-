from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import Group
from .models import User, UserPrivilege

# Unregister the default Group admin
admin.site.unregister(Group)


class UserPrivilegeInline(admin.StackedInline):
    model = UserPrivilege
    can_delete = False
    verbose_name_plural = 'Employee Module Privileges'
    fk_name = 'user'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'mobile_number', 'role', 'institute', 'is_staff')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Institute Access & Tagging', {'fields': ('role', 'institute', 'accessible_institutes', 'mobile_number', 'profile_photo')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Institute Access & Tagging', {'fields': ('role', 'institute', 'accessible_institutes', 'mobile_number', 'profile_photo')}),
    )
    filter_horizontal = ('accessible_institutes', 'groups', 'user_permissions')
    inlines = (UserPrivilegeInline,)

    class Media:
        css = {
            'all': ('admin/css/custom_group_style.css',)
        }


@admin.register(UserPrivilege)
class UserPrivilegeAdmin(admin.ModelAdmin):
    list_display = ('user', 'perm_admissions_overview', 'perm_student_list', 'perm_attendance', 'perm_fee_reports', 'perm_employee_privileges')
    list_filter = ('perm_admissions_overview', 'perm_attendance', 'perm_fee_reports', 'perm_employee_privileges')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email')


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
