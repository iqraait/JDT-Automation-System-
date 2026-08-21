import datetime
from django.db import models
from institutes.models import Institute


#  NEW: COURSE CATEGORY
class CourseCategory(models.Model):
    name = models.CharField(max_length=255)
    
    def __str__(self):
        return self.name


#  NEW: COURSE SUB-CATEGORY (HIERARCHY)
class CourseSubCategory(models.Model):
    category = models.ForeignKey(
        CourseCategory, 
        on_delete=models.CASCADE, 
        related_name='subcategories'
    )
    name = models.CharField(max_length=255) # e.g., 1st Semester, Year 1
    
    def __str__(self):
        return f"{self.category.name} - {self.name}"


#  COURSE
class Course(models.Model):
    institute = models.ForeignKey(
        Institute,
        on_delete=models.CASCADE,
        related_name='courses'
    )
    name = models.CharField(max_length=255)
    
    category = models.ForeignKey(
        CourseCategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='courses'
    )

    course_code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    
    # To be removed after data migration
    course_category_type = models.CharField(max_length=10, default='semester', blank=True, null=True)
    course_category_labels = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"{self.name} ({self.course_code})" if self.course_code else self.name


#  FORM SECTION
class FormSection(models.Model):
    name = models.CharField(max_length=255)
    order = models.IntegerField(default=0)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['order']


#  APPLICATION FORM
class ApplicationForm(models.Model):
    course = models.OneToOneField(
        Course,
        on_delete=models.CASCADE,
        related_name='form'
    )
    title = models.CharField(max_length=255)
    registration_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    payment_config = models.ForeignKey(
        'applications.PaymentConfig', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='forms'
    )
    is_active = models.BooleanField(default=True)
    
    # NEW: CUSTOM NOTIFICATION MESSAGE
    notification_message = models.TextField(blank=True, null=True, help_text="Shown at the top of the student portal")
    
    # NEW: ACADEMIC YEAR FILTERING
    academic_year = models.ForeignKey(
        'institutes.AcademicYear', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='active_forms'
    )

    def __str__(self):
        return self.title


#  NEW: APPLICATION FEE TYPES (BY CATEGORY)
class ApplicationFeeType(models.Model):
    form = models.ForeignKey(
        ApplicationForm, 
        on_delete=models.CASCADE, 
        related_name='fee_types'
    )
    name = models.CharField(max_length=100, help_text="e.g. General, Orphan, Ex-Service")
    amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.form.title} - {self.name} (₹{self.amount})"


#  FIELD TYPES
FIELD_TYPES = (
    ('text', 'Text'),
    ('number', 'Number'),
    ('date', 'Date'),
    ('textarea', 'Textarea'),
    ('select', 'Dropdown'),
    ('radio', 'Radio'),
    ('checkbox', 'Checkbox'),
    ('file', 'File Upload'),
)


#  FORM FIELD
class FormField(models.Model):
    form = models.ForeignKey(
        ApplicationForm,
        on_delete=models.CASCADE,
        related_name='fields'
    )
    section = models.ForeignKey(
        FormSection,
        on_delete=models.CASCADE,
        related_name='fields'
    )

    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=50, choices=FIELD_TYPES)
    is_photo = models.BooleanField(default=False)
    is_signature = models.BooleanField(default=False)
    placeholder = models.CharField(max_length=255, blank=True, null=True)
    required = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    is_name_field = models.BooleanField(
        default=False,
        help_text="Check this if this field is Student Name"
    )

    depends_on = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dependent_fields'
    )
    depends_value = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    def __str__(self):
        return self.label

    class Meta:
        ordering = ['order']


# OPTIONS
class FieldOption(models.Model):
    field = models.ForeignKey(
        FormField,
        on_delete=models.CASCADE,
        related_name='options'
    )
    value = models.CharField(max_length=255)
    display_text = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.field.label} - {self.display_text}"


# QUALIFYING EXAM
class QualifyingExam(models.Model):
    name = models.CharField(max_length=255)
    
    # NEW: COURSE MAPPING
    course = models.ForeignKey(
        Course, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='qualifying_exams'
    )

    def __str__(self):
        if self.course:
            return f"{self.name} - {self.course.name}"
        return self.name


# ✅ SUBJECTS
class ExamSubject(models.Model):
    exam = models.ForeignKey(
        QualifyingExam,
        on_delete=models.CASCADE,
        related_name='subjects'
    )
    name = models.CharField(max_length=255)
    max_marks = models.IntegerField(default=100)
    
    # NEW: PASS MARK CONFIGURATION
    pass_mark = models.IntegerField(default=35)

    include_in_rank = models.BooleanField(default=True)
    is_main_subject = models.BooleanField(default=False)
    is_sub_subject = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.exam.name} - {self.name}"


# ✅ NEW: CLASS MODEL
class Class(models.Model):
    institute = models.ForeignKey(Institute, on_delete=models.CASCADE, related_name='classes')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='classes')
    academic_year = models.ForeignKey('institutes.AcademicYear', on_delete=models.CASCADE, related_name='classes')
    
    # period = Category/Year/Semester level (e.g., Year 1, Sem 1)
    period = models.ForeignKey(CourseSubCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='classes')
    
    name = models.CharField(max_length=100) # e.g., Class A, Division B
    
    # NEW: CATEGORY LINK
    category = models.ForeignKey(CourseCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='classes')

    class Meta:
        verbose_name_plural = "Classes"
        ordering = ['-id']

    def __str__(self):
        period_name = self.period.name if self.period else "General"
        return f"{self.name} ({self.course.name} - {period_name})"


# ✅ NEW: SUBJECT MODEL
class Subject(models.Model):
    institute = models.ForeignKey(Institute, on_delete=models.CASCADE, related_name='all_subjects')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='course_subjects')
    
    # Optional period link for filtering
    period = models.ForeignKey(CourseSubCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='period_subjects')
    
    name = models.CharField(max_length=255)
    subject_code = models.CharField(max_length=50, blank=True, null=True)
    
    # NEW: CATEGORY LINK
    category = models.ForeignKey(CourseCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='period_subjects_v2')
    
    # Linked to classes
    classes = models.ManyToManyField(Class, related_name='subjects', blank=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"{self.name} ({self.course.name})"


# ✅ RELATIONSHIP PORTAL: NOTICE BOARD
class NoticeBoard(models.Model):
    institute = models.ForeignKey(Institute, on_delete=models.CASCADE, related_name='notices')
    title = models.CharField(max_length=255)
    content = models.TextField()
    
    # Targeting
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True, related_name='notices')
    assigned_class = models.ForeignKey(Class, on_delete=models.CASCADE, null=True, blank=True, related_name='notices')
    
    file_attachment = models.FileField(upload_to='notices/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


# ✅ RELATIONSHIP PORTAL: TIMETABLE
class Timetable(models.Model):
    assigned_class = models.OneToOneField(Class, on_delete=models.CASCADE, related_name='timetable')
    image_file = models.ImageField(upload_to='timetables/', help_text="Upload a clean image of the class timetable")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Timetable - {self.assigned_class.name}"


# ✅ RELATIONSHIP PORTAL: ACADEMIC RESULTS
class AcademicResult(models.Model):
    admission = models.ForeignKey('applications.Admission', on_delete=models.CASCADE, related_name='results')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='student_results')
    
    # Semester/Period link
    period = models.ForeignKey(CourseSubCategory, on_delete=models.CASCADE, related_name='period_results')
    
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2)
    max_marks = models.IntegerField(default=100)
    remarks = models.CharField(max_length=255, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('admission', 'subject', 'period')
        ordering = ['period', 'subject']

    def __str__(self):
        return f"{self.admission.application.student.username} - {self.subject.name}"


# ✅ RELATIONSHIP PORTAL: STUDENT DOCUMENTS
class StudentDocument(models.Model):
    admission = models.ForeignKey('applications.Admission', on_delete=models.CASCADE, related_name='uploaded_documents')
    title = models.CharField(max_length=255) # e.g. "Identity Card Copy"
    file = models.FileField(upload_to='student_docs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.admission.application.student.username}"


class ClassYear(models.Model):
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='class_years')
    name = models.CharField(max_length=100, help_text="e.g., Year 1, Year 2, Year 3, Semester 1")
    is_active = models.BooleanField(default=True)
    class Meta:
        verbose_name = "Class Year"
        verbose_name_plural = "Class Years"
        ordering = ['name']
    def __str__(self):
        return f"{self.class_obj.name} - {self.name}"

class FeeCategoryMaster(models.Model):
    name = models.CharField(max_length=100, help_text="e.g., General, Sponsorship, Orphan, Fee Waiver")
    description = models.TextField(blank=True, null=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Percentage discount (0.00 to 100.00)")
    is_active = models.BooleanField(default=True)
    class Meta:
        verbose_name = "Fee Category Master"
        verbose_name_plural = "Fee Category Masters"
    def __str__(self):
        return f"{self.name} ({self.discount_percentage}%)"

class FeeType(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g., Tuition Fee, Sports Fee, Hostel Fee")
    description = models.TextField(blank=True, null=True)
    is_discountable = models.BooleanField(default=True, help_text="Is this fee type eligible for category/custom discounts?")
    is_active = models.BooleanField(default=True)
    class Meta:
        verbose_name = "Fee Type"
        verbose_name_plural = "Fee Types"
    def __str__(self):
        return self.name

class FeeStructure(models.Model):
    academic_year = models.ForeignKey('institutes.AcademicYear', on_delete=models.CASCADE, related_name='fee_structures')
    institute = models.ForeignKey('institutes.Institute', on_delete=models.CASCADE, related_name='fee_structures')
    course = models.ForeignKey('academics.Course', on_delete=models.CASCADE, related_name='fee_structures')
    class_obj = models.ForeignKey('academics.Class', on_delete=models.CASCADE, related_name='fee_structures')
    class_year = models.ForeignKey(ClassYear, on_delete=models.CASCADE, related_name='fee_structures')
    fee_category = models.ForeignKey(FeeCategoryMaster, on_delete=models.CASCADE, related_name='fee_structures')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = "Fee Structure"
        verbose_name_plural = "Fee Structures"
        unique_together = ('academic_year', 'institute', 'course', 'class_obj', 'class_year', 'fee_category')
    def __str__(self):
        return f"{self.course.name} - {self.class_obj.name} ({self.class_year.name}) - {self.fee_category.name}"

class FeeHead(models.Model):
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE, related_name='heads')
    fee_type = models.ForeignKey(FeeType, on_delete=models.PROTECT, related_name='fee_heads')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    due_date = models.DateField()
    fine_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Fine to apply after due date")
    is_active = models.BooleanField(default=True)
    class Meta:
        verbose_name = "Fee Head / Structure Item"
        verbose_name_plural = "Fee Heads / Structure Items"
    def __str__(self):
        return f"{self.fee_type.name}: ₹{self.amount}"

class StudentFeePayment(models.Model):
    admission = models.ForeignKey('applications.Admission', on_delete=models.CASCADE, related_name='fee_payments')
    fee_head = models.ForeignKey(FeeHead, on_delete=models.PROTECT, related_name='payments')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    fine_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_date = models.DateField(default=datetime.date.today)
    payment_mode = models.CharField(
        max_length=50, 
        choices=[('cash', 'Cash'), ('online', 'Online'), ('bank_transfer', 'Bank Transfer')], 
        default='cash'
    )
    reference_no = models.CharField(max_length=100, blank=True, null=True, help_text="Receipt, Transaction ID, etc.")
    receipt_number = models.CharField(max_length=50, blank=True, null=True, db_index=True, help_text="Receipt number for fee payment transaction")
    is_cancelled = models.BooleanField(default=False, db_index=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancellation_reason = models.TextField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = "Student Fee Payment"
        verbose_name_plural = "Student Fee Payments"
    def __str__(self):
        return f"{self.admission.registration_id or self.id} - {self.fee_head.fee_type.name} - ₹{self.amount_paid}"