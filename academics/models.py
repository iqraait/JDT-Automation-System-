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