import datetime
from django.db import models
from accounts.models import User
from institutes.models import Institute, AcademicYear
from academics.models import Course, FormField, CourseSubCategory, ApplicationFeeType


# MAIN APPLICATION
class Application(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    institute = models.ForeignKey(Institute, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, null=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    
    # NEW: Store selected fee category
    selected_fee_type = models.ForeignKey(
        ApplicationFeeType, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )

    #  ADD THIS HERE
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('selected', 'Selected'),
            ('rejected', 'Rejected'),
            ('hold', 'On Hold'),
        ],
        default='pending'
    )

    remarks = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def display_name(self):
        """
        Robustly returns student name:
        1. User first_name
        2. Form field marked as is_name_field
        3. Form field containing 'name'
        4. Username fallback
        """
        if self.student.first_name:
            return self.student.first_name

        # Avoid redundant DB hits if field_values is pre-fetched
        for fv in self.field_values.all():
            if fv.field and getattr(fv.field, 'is_name_field', False):
                return fv.value
            
        # secondary check for common labels if no flag is set
        for fv in self.field_values.all():
            field_label = fv.field.label if fv.field else fv.field_label
            if field_label:
                label = field_label.lower()
                if "name" in label and ":" not in str(fv.value):
                    return fv.value

        return self.student.username

    def __str__(self):
        return f"{self.display_name} - Application #{self.id}"

#   NEW TABLE (IMPORTANT)
class ApplicationFieldValue(models.Model):
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='field_values'
    )
    # Changed to SET_NULL for Data Safety (Part 6)
    field = models.ForeignKey(FormField, on_delete=models.SET_NULL, null=True, blank=True)

    # Snapshot fields to preserve data even if FormField is deleted
    field_label = models.CharField(max_length=255, blank=True, null=True)
    field_type = models.CharField(max_length=50, blank=True, null=True)

    value = models.TextField(blank=True, null=True)

    def __str__(self):
        label = self.field.label if self.field else self.field_label
        return f"{self.application.id} - {label}"
    

from django.db import models
from .models import Application  # adjust if needed


# 🔥 GLOBAL CHOICES (BEST PRACTICE)
GATEWAY_CHOICES = [
    ('ccavenue', 'CCAvenue'),
    ('phicommerce', 'PhiCommerce'),
]

ENV_CHOICES = [
    ('uat', 'UAT'),
    ('prod', 'Production'),
]

PAYMENT_MODE_CHOICES = [
    ('CARD', 'Card'),
    ('NB', 'NetBanking'),
    ('UPI', 'UPI'),
]


# =============================================================================
# PAYMENT CONFIGURATION
# =============================================================================
class PaymentConfig(models.Model):
    name = models.CharField(max_length=100)
    gateway_type = models.CharField(max_length=20, choices=GATEWAY_CHOICES)

    merchant_id = models.CharField(max_length=255, blank=True, null=True)

    # CCAvenue
    access_code = models.CharField(max_length=255, blank=True, null=True)
    working_key = models.CharField(max_length=255, blank=True, null=True)

    # PhiCommerce
    secret_key = models.CharField(max_length=255, blank=True, null=True)
    terminal_id = models.CharField(max_length=255, blank=True, null=True)

    # Environment
    environment = models.CharField(max_length=10, choices=ENV_CHOICES, default='uat')
    base_url = models.CharField(max_length=255, blank=True, null=True)
    callback_url = models.URLField(blank=True, null=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.gateway_type})"


# =============================================================================
# PAYMENT MODEL
# =============================================================================
class Payment(models.Model):
    application = models.OneToOneField(Application, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=8, decimal_places=2)

    gateway_config = models.ForeignKey(
        PaymentConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Tracking
    merchant_txn_no = models.CharField(max_length=255, blank=True, null=True)
    tran_ctx = models.CharField(max_length=255, blank=True, null=True)
    gateway_transaction_id = models.CharField(max_length=255, blank=True, null=True)

    payment_mode = models.CharField(
        max_length=10,
        choices=PAYMENT_MODE_CHOICES,
        blank=True,
        null=True
    )

    gateway_response = models.JSONField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('success', 'Success'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.application.id} - {self.status}"

# #  PAYMENT CONFIGURATION
# class PaymentConfig(models.Model):
#     GATEWAY_CHOICES = [
#         ('ccavenue', 'CCAvenue'),
#         ('phicommerce', 'PhiCommerce'),
#     ]
    
#     name = models.CharField(max_length=100, help_text="e.g. CCAvenue Production, PhiCommerce UAT")
#     gateway_type = models.CharField(max_length=20, choices=GATEWAY_CHOICES)
    
#     # CCAvenue specific
#     merchant_id = models.CharField(max_length=255, blank=True, null=True)
#     access_code = models.CharField(max_length=255, blank=True, null=True)
#     working_key = models.CharField(max_length=255, blank=True, null=True)
#     # PhiCommerce specific
#     secret_key = models.CharField(max_length=255, blank=True, null=True)
#     terminal_id = models.CharField(max_length=255, blank=True, null=True)
    
#     is_active = models.BooleanField(default=True)

#     def __str__(self):
#         return f"{self.name} ({self.gateway_type})"


# #  PAYMENT MODEL
# class Payment(models.Model):
#     application = models.OneToOneField(Application, on_delete=models.CASCADE)
#     amount = models.DecimalField(max_digits=8, decimal_places=2)
    
#     gateway_config = models.ForeignKey(PaymentConfig, on_delete=models.SET_NULL, null=True, blank=True)
#     gateway_transaction_id = models.CharField(max_length=255, null=True, blank=True)
#     gateway_response = models.JSONField(null=True, blank=True)

#     status = models.CharField(
#         max_length=20,
#         choices=[
#             ('pending', 'Pending'),
#             ('success', 'Success'),
#             ('failed', 'Failed'),
#         ],
#         default='pending'
#     )

#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"Payment {self.application.id} - {self.status}"


#  FEE CATEGORY MODEL
class FeeCategory(models.Model):
    name = models.CharField(max_length=100) # General, Orphan, etc.
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='fee_categories')
    total_fee = models.DecimalField(max_digits=10, decimal_places=2)
    
    # [DEPRECATED] category_type will be derived from course.category
    category_type = models.CharField(max_length=50, blank=True, null=True)
    
    # Example: [100, 100, 100] for 3 semesters
    breakdown = models.JSONField(default=list, help_text="List of fee amounts per period")

    def __str__(self):
        return f"{self.name} - {self.course.name} ({self.total_fee})"

class FeeSubCategory(models.Model):
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=255) # Tuition Fee, Lab Fee, etc.
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} - {self.amount}"


#  STUDENT ADMISSION MODEL
class Admission(models.Model):
    ADMISSION_STATUS = [
        ('active', 'Active'),
        ('warned', 'Warned'),
        ('suspended', 'Suspended'),
        ('trashed', 'Trashed'),
    ]

    application = models.OneToOneField(
        Application, 
        on_delete=models.CASCADE, 
        related_name='admission', 
        null=True, 
        blank=True
    )
    
    # Registration Info
    registration_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    register_number = models.CharField(max_length=100, unique=True, null=True, blank=True, db_index=True)
    annual_serial = models.IntegerField(default=1)

    date_of_join = models.DateField()
    selected_course = models.ForeignKey(Course, on_delete=models.PROTECT)
    
    # Track which period they joined from (e.g., 2nd Sem)
    joining_period = models.ForeignKey(
        CourseSubCategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='admissions'
    )
    
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.PROTECT)
    
    # NEW: Assigned Class
    assigned_class = models.ForeignKey('academics.Class', on_delete=models.SET_NULL, null=True, blank=True, related_name='admissions')
    
    calculated_fee = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_reason = models.TextField(blank=True, null=True)
    final_fee = models.DecimalField(max_digits=10, decimal_places=2)

    # Status Management
    status = models.CharField(max_length=20, choices=ADMISSION_STATUS, default='active', db_index=True)
    status_reason = models.TextField(blank=True, null=True)
    status_updated_at = models.DateTimeField(auto_now=True)

    # Guardian Details
    care_of = models.CharField(max_length=255, blank=True, null=True)
    guardian_name = models.CharField(max_length=255)
    guardian_mobile = models.CharField(max_length=20)
    relationship = models.CharField(max_length=100)
    guardian_address = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # Robust safety: Ensure date_of_join is a date object
        if isinstance(self.date_of_join, str):
            try:
                self.date_of_join = datetime.datetime.strptime(self.date_of_join, '%Y-%m-%d').date()
            except ValueError:
                self.date_of_join = datetime.date.today()

        if not self.register_number:
            # Format: <course_code>/<year>/<serial_number>
            # Use AcademicYear if available, else current year
            year_val = self.application.academic_year.name if (self.application and self.application.academic_year) else self.date_of_join.year
            
            course_code = self.selected_course.course_code or "GEN"
            
            # Reset serial each year per course
            last_admission = Admission.objects.filter(
                selected_course=self.selected_course,
                created_at__year=self.created_at.year if self.created_at else datetime.date.today().year
            ).order_by('-annual_serial').first()
            
            if last_admission:
                self.annual_serial = last_admission.annual_serial + 1
            else:
                self.annual_serial = 1
                
            self.register_number = f"{course_code}/{year_val}/{self.annual_serial}"
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.register_number or self.registration_id} - {self.guardian_name}"