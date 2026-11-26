from django.contrib import admin
from .models import Institute, AcademicYear


@admin.register(Institute)
class InstituteAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'user', 'address']
    search_fields = ['name', 'code', 'address', 'user__username', 'user__email']
    ordering = ['name']


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'institute', 'start_date', 'end_date', 'is_active']
    search_fields = ['name', 'institute__name', 'institute__code']
    list_filter = ['is_active', 'institute']
    list_editable = ['is_active']
    ordering = ['-name']
