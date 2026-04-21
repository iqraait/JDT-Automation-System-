from django.contrib import admin
from .models import (
    Course,
    CourseCategory,
    CourseSubCategory,
    FormSection,
    ApplicationForm,
    FormField,
    FieldOption,
    QualifyingExam,
    ExamSubject,
    Class,
    Subject
)


class ApplicationFormListFilter(admin.SimpleListFilter):
    title = 'Application Form'
    parameter_name = 'form'

    def lookups(self, request, model_admin):
        # Using late import or looking up through model record
        from .models import ApplicationForm
        forms = ApplicationForm.objects.all().order_by('title')
        return [(f.id, f.title) for f in forms]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(form_id=self.value())
        return queryset


@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name']


@admin.register(CourseSubCategory)
class CourseSubCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['name', 'course_code', 'category', 'institute']
    search_fields = ['name', 'course_code']
    list_filter = ['category', 'institute']


@admin.register(FormSection)
class FormSectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'order']


@admin.register(ApplicationForm)
class ApplicationFormAdmin(admin.ModelAdmin):
    list_display = ['course', 'title', 'academic_year', 'registration_fee', 'payment_config', 'is_active']
    list_filter = ['academic_year', 'is_active', 'course']
    list_editable = ['is_active']
    search_fields = ['title', 'course__name']


class FieldOptionInline(admin.TabularInline):
    model = FieldOption
    extra = 1


@admin.register(FormField)
class FormFieldAdmin(admin.ModelAdmin):
    list_display = [
        'label',
        'field_type',
        'section',
        'form',
        'order',
        'is_name_field',
        'is_photo', 
        'is_signature'
    ]

    list_filter = [ApplicationFormListFilter, 'field_type', 'section']
    search_fields = ['label', 'form__title']

    fields = [
        'form',
        'section',
        'label',
        'field_type',
        'placeholder',
        'required',
        'order',
        'is_name_field',   
        'depends_on',
        'depends_value',
        'is_photo', 
        'is_signature'
    ]

    inlines = [FieldOptionInline]


@admin.register(QualifyingExam)
class QualifyingExamAdmin(admin.ModelAdmin):
    list_display = ['name', 'course']
    list_filter = ['course']


@admin.register(ExamSubject)
class ExamSubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'exam', 'max_marks', 'pass_mark', 'include_in_rank', 'is_main_subject', 'is_sub_subject']
    list_filter = ['exam', 'include_in_rank', 'is_main_subject', 'is_sub_subject']
    search_fields = ['name']


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'course', 'category', 'period', 'academic_year', 'institute']
    list_filter = ['course', 'category', 'academic_year', 'institute', 'period']
    search_fields = ['name']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'subject_code', 'course', 'category', 'period', 'institute']
    list_filter = ['course', 'category', 'institute', 'period']
    search_fields = ['name', 'subject_code']
    filter_horizontal = ['classes']