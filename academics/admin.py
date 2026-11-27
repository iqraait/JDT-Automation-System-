from django.contrib import admin
from django.db.models import Q
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
    StudentFeePayment,
    FeeRefundRequest,
    FeeRefundRequestItem
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

def advance_date_by_years(orig_date, years=1):
    if not orig_date:
        return orig_date
    try:
        return orig_date.replace(year=orig_date.year + years)
    except ValueError:
        return orig_date.replace(year=orig_date.year + years, day=28)


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ['academic_year', 'institute', 'course', 'class_obj', 'class_year', 'fee_category', 'auto_assign', 'duplicate_link']
    list_filter = ['academic_year', 'institute', 'course', 'class_obj', 'class_year', 'fee_category', 'auto_assign']
    actions = ['duplicate_selected_fee_structures']
    inlines = [FeeHeadInline]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from django.contrib import messages
        if obj.auto_assign and obj.class_obj:
            count = obj.assign_to_class_students()
            if count > 0:
                self.message_user(
                    request,
                    f"Auto-assigned fee structure ({obj.class_year.name} - {obj.fee_category.name}) to {count} student(s) in {obj.class_obj.name}.",
                    level=messages.SUCCESS
                )
            else:
                self.message_user(
                    request,
                    f"Fee structure saved with Auto-Assign enabled, but no active student(s) found in {obj.class_obj.name} matching this criteria.",
                    level=messages.WARNING
                )

    def duplicate_link(self, obj):
        from django.utils.html import format_html
        return format_html('<a class="button" href="/admin/academics/feestructure/{}/duplicate/" style="background-color: #2563eb; color: white !important; font-weight: bold; padding: 4px 8px; border-radius: 4px; text-decoration: none;">Duplicate</a>', obj.id)
    duplicate_link.short_description = "Copy Structure"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('bulk-duplicate/', self.admin_site.admin_view(self.bulk_duplicate_view), name='academics_feestructure_bulk_duplicate'),
            path('<int:object_id>/duplicate/', self.admin_site.admin_view(self.duplicate_view), name='academics_feestructure_duplicate'),
        ]
        return custom_urls + urls

    def duplicate_view(self, request, object_id):
        from django import forms
        from django.shortcuts import render, redirect
        from django.contrib import messages
        from institutes.models import AcademicYear, Institute, log_activity
        
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
            auto_assign = forms.BooleanField(
                required=False,
                initial=False,
                label="Auto Assign to Class Students",
                help_text="If checked, automatically assigns this fee structure to all students in the selected class."
            )
 
        if request.method == 'POST':
            form = DuplicateForm(request.POST)
            if form.is_valid():
                academic_year = form.cleaned_data['academic_year']
                institute = form.cleaned_data['institute']
                course = form.cleaned_data['course']
                class_obj = form.cleaned_data['class_obj']
                class_year = form.cleaned_data['class_year']
                fee_category = form.cleaned_data['fee_category']
                auto_assign = form.cleaned_data.get('auto_assign', False)
 
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
                        fee_category=fee_category,
                        auto_assign=auto_assign
                    )
                    if auto_assign:
                        new_struct.assign_to_class_students()
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
                    
                    log_activity(
                        user=request.user,
                        module="Academic Settings",
                        activity=f"Duplicated fee structure (ID: {obj.id}) to new structure (ID: {new_struct.id})",
                        institute=new_struct.institute
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

    def bulk_duplicate_view(self, request):
        """Bulk duplicate all fee structures from one Academic Year and/or Institute to another."""
        from django import forms
        from django.shortcuts import render, redirect
        from django.contrib import messages
        from institutes.models import AcademicYear, Institute, log_activity

        class BulkDuplicateForm(forms.Form):
            source_academic_year = forms.ModelChoiceField(
                queryset=AcademicYear.objects.all().order_by('-name'),
                label="Source Academic Year",
                help_text="Year to copy structures FROM"
            )
            target_academic_year = forms.ModelChoiceField(
                queryset=AcademicYear.objects.all().order_by('-name'),
                label="Target Academic Year",
                help_text="Year to copy structures TO"
            )
            source_institute = forms.ModelChoiceField(
                queryset=Institute.objects.all().order_by('name'),
                required=False,
                empty_label="-- All Institutes --",
                label="Source Institute",
                help_text="Leave empty to duplicate across all institutes, or choose one"
            )
            target_institute = forms.ModelChoiceField(
                queryset=Institute.objects.all().order_by('name'),
                required=False,
                empty_label="-- Same Institute as Source --",
                label="Target Institute",
                help_text="Choose a specific institute to duplicate to, or leave empty to keep same institute"
            )
            advance_dates_by_years = forms.IntegerField(
                initial=1,
                min_value=0,
                max_value=10,
                label="Advance Fee Dates By (Years)",
                help_text="Number of years to advance start_date and due_date in Fee Heads (default: 1)"
            )
            skip_existing = forms.BooleanField(
                initial=True,
                required=False,
                label="Skip Existing Structures",
                help_text="If checked, skip any fee structure that already exists in the target year/institute"
            )

        if request.method == 'POST':
            form = BulkDuplicateForm(request.POST)
            if form.is_valid():
                source_year = form.cleaned_data['source_academic_year']
                target_year = form.cleaned_data['target_academic_year']
                source_inst = form.cleaned_data['source_institute']
                target_inst = form.cleaned_data['target_institute']
                adv_years = form.cleaned_data['advance_dates_by_years']
                skip_exist = form.cleaned_data['skip_existing']

                if source_year == target_year and (source_inst == target_inst or not target_inst):
                    form.add_error(None, "Source and Target cannot be identical without a different Target Institute.")
                else:
                    structures_qs = FeeStructure.objects.filter(academic_year=source_year)
                    if source_inst:
                        structures_qs = structures_qs.filter(institute=source_inst)

                    if not structures_qs.exists():
                        form.add_error(None, f"No fee structures found for {source_year.name}.")
                    else:
                        created_count = 0
                        skipped_count = 0
                        heads_count = 0

                        for struct in structures_qs:
                            dest_inst = target_inst if target_inst else struct.institute
                            exists = FeeStructure.objects.filter(
                                academic_year=target_year,
                                institute=dest_inst,
                                course=struct.course,
                                class_obj=struct.class_obj,
                                class_year=struct.class_year,
                                fee_category=struct.fee_category
                            ).exists()

                            if exists:
                                if skip_exist:
                                    skipped_count += 1
                                    continue

                            new_struct = FeeStructure.objects.create(
                                academic_year=target_year,
                                institute=dest_inst,
                                course=struct.course,
                                class_obj=struct.class_obj,
                                class_year=struct.class_year,
                                fee_category=struct.fee_category
                            )
                            created_count += 1

                            for head in struct.heads.all():
                                new_start = advance_date_by_years(head.start_date, adv_years)
                                new_due = advance_date_by_years(head.due_date, adv_years)
                                FeeHead.objects.create(
                                    fee_structure=new_struct,
                                    fee_type=head.fee_type,
                                    amount=head.amount,
                                    start_date=new_start,
                                    due_date=new_due,
                                    fine_amount=head.fine_amount,
                                    is_active=head.is_active
                                )
                                heads_count += 1

                        log_activity(
                            user=request.user,
                            module="Fee Configuration",
                            activity=f"Bulk duplicated {created_count} fee structures ({heads_count} heads) from {source_year.name} to {target_year.name} (Skipped {skipped_count})",
                            institute=source_inst or None
                        )

                        messages.success(
                            request,
                            f"Successfully bulk duplicated {created_count} fee structure(s) with {heads_count} fee heads from '{source_year.name}' to '{target_year.name}'! (Skipped {skipped_count} existing)"
                        )
                        return redirect('admin:academics_feestructure_changelist')
        else:
            form = BulkDuplicateForm()

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'form': form,
            'title': 'Bulk Duplicate Fee Structures by Year / Institute',
        }
        return render(request, 'admin/academics/feestructure/bulk_duplicate.html', context)

    def duplicate_selected_fee_structures(self, request, queryset):
        """Admin action: Duplicate selected fee structures to a target Academic Year / Institute."""
        from django import forms
        from django.shortcuts import render
        from django.contrib import messages
        from institutes.models import AcademicYear, Institute, log_activity

        class ActionDuplicateForm(forms.Form):
            target_academic_year = forms.ModelChoiceField(
                queryset=AcademicYear.objects.all().order_by('-name'),
                label="Target Academic Year"
            )
            target_institute = forms.ModelChoiceField(
                queryset=Institute.objects.all().order_by('name'),
                required=False,
                empty_label="-- Keep Same Institute as Source --",
                label="Target Institute"
            )
            advance_dates_by_years = forms.IntegerField(
                initial=1, min_value=0, max_value=10, label="Advance Fee Dates By (Years)"
            )
            skip_existing = forms.BooleanField(
                initial=True, required=False, label="Skip Existing Structures"
            )

        if 'apply' in request.POST:
            form = ActionDuplicateForm(request.POST)
            if form.is_valid():
                target_year = form.cleaned_data['target_academic_year']
                target_inst = form.cleaned_data['target_institute']
                adv_years = form.cleaned_data['advance_dates_by_years']
                skip_exist = form.cleaned_data['skip_existing']

                created_count = 0
                skipped_count = 0
                heads_count = 0

                for struct in queryset:
                    dest_inst = target_inst if target_inst else struct.institute
                    exists = FeeStructure.objects.filter(
                        academic_year=target_year,
                        institute=dest_inst,
                        course=struct.course,
                        class_obj=struct.class_obj,
                        class_year=struct.class_year,
                        fee_category=struct.fee_category
                    ).exists()

                    if exists:
                        if skip_exist:
                            skipped_count += 1
                            continue

                    new_struct = FeeStructure.objects.create(
                        academic_year=target_year,
                        institute=dest_inst,
                        course=struct.course,
                        class_obj=struct.class_obj,
                        class_year=struct.class_year,
                        fee_category=struct.fee_category
                    )
                    created_count += 1

                    for head in struct.heads.all():
                        new_start = advance_date_by_years(head.start_date, adv_years)
                        new_due = advance_date_by_years(head.due_date, adv_years)
                        FeeHead.objects.create(
                            fee_structure=new_struct,
                            fee_type=head.fee_type,
                            amount=head.amount,
                            start_date=new_start,
                            due_date=new_due,
                            fine_amount=head.fine_amount,
                            is_active=head.is_active
                        )
                        heads_count += 1

                log_activity(
                    user=request.user,
                    module="Fee Configuration",
                    activity=f"Action duplicated {created_count} fee structures ({heads_count} heads) to {target_year.name} (Skipped {skipped_count})",
                    institute=None
                )

                self.message_user(
                    request,
                    f"Successfully duplicated {created_count} selected structure(s) with {heads_count} fee heads to '{target_year.name}'! (Skipped {skipped_count} existing)",
                    level=messages.SUCCESS
                )
                return None
        else:
            form = ActionDuplicateForm()

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'queryset': queryset,
            'form': form,
            'title': f'Duplicate {queryset.count()} Selected Fee Structure(s)',
        }
        return render(request, 'admin/academics/feestructure/confirm_bulk_duplicate.html', context)
    duplicate_selected_fee_structures.short_description = "Duplicate selected fee structures to another Year/Institute"


class PaymentCollegeFilter(admin.SimpleListFilter):
    title = 'Institute / College'
    parameter_name = 'institute'

    def lookups(self, request, model_admin):
        from institutes.models import Institute
        return [(inst.id, inst.name) for inst in Institute.objects.all().order_by('name')]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                Q(admission__selected_course__institute_id=self.value()) |
                Q(admission__application__institute_id=self.value()) |
                Q(fee_head__fee_structure__institute_id=self.value())
            ).distinct()
        return queryset


@admin.register(StudentFeePayment)
class StudentFeePaymentAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'display_admission', 'fee_head', 'amount_paid', 'fine_paid', 'payment_date', 'payment_mode', 'reference_no', 'is_cancelled']
    list_filter = [PaymentCollegeFilter, 'payment_mode', 'payment_date', 'is_cancelled']
    search_fields = [
        'receipt_number',
        'admission__registration_id',
        'admission__register_number',
        'admission__guardian_name',
        'admission__application__field_values__value',
        'admission__application__student__username',
        'admission__application__student__first_name',
        'reference_no'
    ]
    actions = ['delete_selected_payments_and_restore_dues']

    def display_admission(self, obj):
        if not obj.admission:
            return "-"
        adm_no = obj.admission.registration_id or obj.admission.register_number or f"#{obj.admission.id}"
        return f"{adm_no} - {obj.admission.student_name}"
    display_admission.short_description = 'Admission (Adm No - Student Name)'
    display_admission.admin_order_field = 'admission__registration_id'

    def delete_selected_payments_and_restore_dues(self, request, queryset):
        """Admin action to permanently delete selected payments and restore dues."""
        from django.contrib import messages
        from institutes.models import log_activity
        if not (request.user.is_superuser or request.user.has_privilege('perm_delete_fee_collection')):
            self.message_user(request, "Permission Denied: You do not have privilege to delete fee collections & receipts.", level=messages.ERROR)
            return

        count = queryset.count()
        total_amount = sum(float(p.amount_paid + p.fine_paid) for p in queryset)
        receipts = list(queryset.values_list('receipt_number', flat=True).distinct())

        queryset.delete()

        log_activity(
            user=request.user,
            module="Fee Management",
            activity=f"Admin deleted {count} payment records ({len(receipts)} receipts) totaling ₹{total_amount:.2f}. Restored student dues.",
            institute=None
        )

        self.message_user(
            request,
            f"Successfully deleted {count} payment records ({len(receipts)} receipts) totaling ₹{total_amount:.2f}. Student outstanding dues have been restored.",
            level=messages.SUCCESS
        )
    delete_selected_payments_and_restore_dues.short_description = "Delete selected fee collections & restore student dues"



class FeeRefundRequestItemInline(admin.TabularInline):
    model = FeeRefundRequestItem
    extra = 1

@admin.register(FeeRefundRequest)
class FeeRefundRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'admission', 'amount', 'status', 'requested_by', 'requested_at', 'approved_at']
    list_filter = ['status', 'institute', 'requested_at']
    search_fields = ['admission__register_number', 'admission__registration_id', 'reason', 'cancellation_reason']
    inlines = [FeeRefundRequestItemInline]
