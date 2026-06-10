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
    Subject,
    NoticeBoard,
    Timetable,
    AcademicResult,
    StudentDocument,
    ApplicationFeeType,
    ClassYear,
    FeeCategoryMaster,
    FeeType,
    FeeStructure,
    FeeHead,
    StudentFeePayment
)


@admin.register(NoticeBoard)
class NoticeBoardAdmin(admin.ModelAdmin):
    list_display = ['title', 'institute', 'course', 'assigned_class', 'is_active', 'created_at']
    list_filter = ['institute', 'course', 'is_active']
    search_fields = ['title', 'content']


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ['assigned_class', 'updated_at']


@admin.register(AcademicResult)
class AcademicResultAdmin(admin.ModelAdmin):
    list_display = ['admission', 'subject', 'period', 'marks_obtained', 'max_marks']
    list_filter = ['period', 'subject']
    search_fields = ['admission__application__student__username']


@admin.register(StudentDocument)
class StudentDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'admission', 'uploaded_at']
    search_fields = ['title', 'admission__application__student__username']


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


class ApplicationFeeTypeInline(admin.TabularInline):
    model = ApplicationFeeType
    extra = 1

@admin.register(FormSection)
class FormSectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'order']


@admin.register(ApplicationForm)
class ApplicationFormAdmin(admin.ModelAdmin):
    list_display = ['course', 'title', 'academic_year', 'registration_fee', 'payment_config', 'is_active']
    list_filter = ['academic_year', 'is_active', 'course']
    list_editable = ['is_active']
    search_fields = ['title', 'course__name']
    inlines = [ApplicationFeeTypeInline]


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


class FeeHeadInline(admin.TabularInline):
    model = FeeHead
    extra = 1

@admin.register(ClassYear)
class ClassYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'class_obj', 'is_active']
    list_filter = ['class_obj', 'is_active']

@admin.register(FeeCategoryMaster)
class FeeCategoryMasterAdmin(admin.ModelAdmin):
    list_display = ['name', 'discount_percentage', 'is_active']
    search_fields = ['name']

@admin.register(FeeType)
class FeeTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_discountable', 'is_active']
    search_fields = ['name']

@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ['academic_year', 'institute', 'course', 'class_obj', 'class_year', 'fee_category']
    list_filter = ['academic_year', 'institute', 'course', 'class_obj', 'class_year', 'fee_category']
    inlines = [FeeHeadInline]

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<int:object_id>/duplicate/', self.admin_site.admin_view(self.duplicate_view), name='academics_feestructure_duplicate'),
        ]
        return custom_urls + urls

    def duplicate_view(self, request, object_id):
        from django import forms
        from django.shortcuts import render, redirect
        from django.contrib import messages
        
        obj = self.get_object(request, object_id)
        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, self.model._meta, object_id)

        class DuplicateForm(forms.Form):
            academic_year = forms.ModelChoiceField(queryset=AcademicYear.objects.filter(is_active=True))
            institute = forms.ModelChoiceField(queryset=Institute.objects.all())
            course = forms.ModelChoiceField(queryset=Course.objects.all())
            class_obj = forms.ModelChoiceField(queryset=Class.objects.all(), label="Class")
            class_year = forms.ModelChoiceField(queryset=ClassYear.objects.all())
            fee_category = forms.ModelChoiceField(queryset=FeeCategoryMaster.objects.all())

        if request.method == 'POST':
            form = DuplicateForm(request.POST)
            if form.is_valid():
                academic_year = form.cleaned_data['academic_year']
                institute = form.cleaned_data['institute']
                course = form.cleaned_data['course']
                class_obj = form.cleaned_data['class_obj']
                class_year = form.cleaned_data['class_year']
                fee_category = form.cleaned_data['fee_category']

                # Check unique_together constraint
                exists = FeeStructure.objects.filter(
                    academic_year=academic_year,
                    institute=institute,
                    course=course,
                    class_obj=class_obj,
                    class_year=class_year,
                    fee_category=fee_category
                ).exists()

                if exists:
                    form.add_error(None, "A fee structure with this combination already exists.")
                else:
                    new_struct = FeeStructure.objects.create(
                        academic_year=academic_year,
                        institute=institute,
                        course=course,
                        class_obj=class_obj,
                        class_year=class_year,
                        fee_category=fee_category
                    )
                    # Copy FeeHead objects
                    for head in obj.heads.all():
                        FeeHead.objects.create(
                            fee_structure=new_struct,
                            fee_type=head.fee_type,
                            amount=head.amount,
                            start_date=head.start_date,
                            due_date=head.due_date,
                            fine_amount=head.fine_amount,
                            is_active=head.is_active
                        )
                    messages.success(request, f"Fee structure duplicated successfully.")
                    return redirect(f'/admin/academics/feestructure/{new_struct.id}/change/')
        else:
            form = DuplicateForm(initial={
                'academic_year': obj.academic_year,
                'institute': obj.institute,
                'course': obj.course,
                'class_obj': obj.class_obj,
                'class_year': obj.class_year,
                'fee_category': obj.fee_category,
            })

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'form': form,
            'object': obj,
            'title': f'Duplicate {obj}',
        }
        return render(request, 'admin/academics/feestructure/duplicate.html', context)

@admin.register(StudentFeePayment)
class StudentFeePaymentAdmin(admin.ModelAdmin):
    list_display = ['admission', 'fee_head', 'amount_paid', 'fine_paid', 'payment_date', 'payment_mode', 'reference_no']
    list_filter = ['payment_mode', 'payment_date']
    search_fields = ['admission__register_number', 'reference_no']