from django.contrib import admin
from .models import Application, FeeCategory, Admission, Payment, PaymentConfig, ApplicationFieldValue
from django.utils.safestring import mark_safe
from django.conf import settings


class ApplicationFieldValueInline(admin.TabularInline):
    model = ApplicationFieldValue
    extra = 0
    readonly_fields = ('field', 'field_label', 'field_type', 'value', 'image_preview')
    fields = ('field', 'field_label', 'field_type', 'value', 'image_preview')

    def image_preview(self, obj):
        if not obj.value:
            return ""
        
        # Check if it's an image based on field flags or labels
        field_label = obj.field.label if obj.field else obj.field_label
        field_type = obj.field.field_type if obj.field else obj.field_type
        
        if not field_label:
            return "No Preview"
            
        label = field_label.lower()
        is_photo = getattr(obj.field, 'is_photo', False) if obj.field else False
        is_signature = getattr(obj.field, 'is_signature', False) if obj.field else False
        
        if field_type == 'file' and (is_photo or is_signature or "photo" in label or "signature" in label or "passport" in label):
            url = f"{settings.MEDIA_URL}{obj.value}"
            # Signature usually needs a wide thumbnail, photo a tall one
            height = "40px" if "signature" in label else "80px"
            return mark_safe(f'<img src="{url}" style="max-height: {height}; border: 1px solid #ccc; border-radius: 4px;" />')
        return "No Preview"
    
    image_preview.short_description = 'Preview'


from django import forms

class ApplicationAdminForm(forms.ModelForm):
    student_email = forms.EmailField(required=False, label="Student Email (Updateable)")

    class Meta:
        model = Application
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.student:
            self.fields['student_email'].initial = self.instance.student.email

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    form = ApplicationAdminForm
    list_display = ['id', 'display_student_name', 'course', 'academic_year', 'status', 'created_at']
    list_filter = ['status', 'course', 'academic_year']
    search_fields = ['student__username', 'student__first_name']
    inlines = [ApplicationFieldValueInline]
    
    def save_model(self, request, obj, form, change):
        email = form.cleaned_data.get('student_email')
        if email and obj.student:
            obj.student.email = email
            obj.student.save()
        super().save_model(request, obj, form, change)

    def display_student_name(self, obj):
        return obj.display_name
    display_student_name.short_description = 'Student'


@admin.register(FeeCategory)
class FeeCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'course', 'total_fee', 'category_type']
    list_filter = ['course', 'category_type']


@admin.register(Admission)
class AdmissionAdmin(admin.ModelAdmin):
    list_display = ['registration_id', 'guardian_name', 'selected_course', 'final_fee', 'date_of_join']
    search_fields = ['registration_id', 'guardian_name', 'guardian_mobile']
    list_filter = ['selected_course', 'date_of_join']


@admin.register(PaymentConfig)
class PaymentConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'gateway_type', 'is_active']
    list_filter = ['gateway_type', 'is_active']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['application', 'amount', 'status', 'gateway_config', 'gateway_transaction_id', 'created_at']
    list_filter = ['status', 'gateway_config', 'created_at']
    search_fields = ['application__student__username', 'gateway_transaction_id']
    readonly_fields = ['formatted_response']

    def formatted_response(self, obj):
        import json
        from django.utils.html import format_html
        if obj.gateway_response:
            formatted = json.dumps(obj.gateway_response, indent=2)
            return format_html('<pre>{}</pre>', formatted)
        return "-"
    formatted_response.short_description = "Bank Response Detail"