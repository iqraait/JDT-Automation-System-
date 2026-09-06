from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('institute', 'Institute'),
    )

    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    mobile_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    profile_photo = models.ImageField(upload_to='student_photos/', null=True, blank=True)

    # 🔥 LINK USER → DEFAULT INSTITUTE
    institute = models.ForeignKey(
        'institutes.Institute',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )

    # MULTI-INSTITUTE ACCESSIBILITY TAGGING
    accessible_institutes = models.ManyToManyField(
        'institutes.Institute',
        blank=True,
        related_name='staff_members'
    )

    def get_accessible_institutes(self):
        from institutes.models import Institute
        if self.is_superuser:
            return list(Institute.objects.all())
        qs = list(self.accessible_institutes.all())
        if self.institute and self.institute not in qs:
            qs.append(self.institute)
        return qs

    def get_active_institute(self, request=None):
        if request and hasattr(request, 'session'):
            active_id = request.session.get('active_institute_id')
            if active_id:
                from institutes.models import Institute
                inst = Institute.objects.filter(id=active_id).first()
                accessible = self.get_accessible_institutes()
                if inst and (self.is_superuser or inst in accessible):
                    return inst
        return self.institute

    def has_privilege(self, perm_name):
        if self.is_superuser or self.role == 'student':
            return True
        if hasattr(self, 'privileges') and self.privileges:
            return getattr(self.privileges, perm_name, True)
        return True

    def __str__(self):
        return self.first_name if self.first_name else self.username


class UserPrivilege(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='privileges')

    # Admissions Module
    perm_admissions_overview = models.BooleanField(default=True, verbose_name="Admissions Overview")
    perm_student_registration = models.BooleanField(default=True, verbose_name="Student Registration")
    perm_student_list = models.BooleanField(default=True, verbose_name="Student List")
    perm_rank_list = models.BooleanField(default=True, verbose_name="Rank List")

    # Academic Operations
    perm_attendance = models.BooleanField(default=True, verbose_name="Attendance Marker")
    perm_notices = models.BooleanField(default=True, verbose_name="News & Notice Board")
    perm_timetables = models.BooleanField(default=True, verbose_name="Class Timetables")
    perm_academic_results = models.BooleanField(default=True, verbose_name="Enter Results")
    perm_course_inventory = models.BooleanField(default=True, verbose_name="Course Inventory")

    # Fee & Financials
    perm_fee_reports = models.BooleanField(default=True, verbose_name="Fee Reports & Dues")
    perm_fee_receipts = models.BooleanField(default=True, verbose_name="Fee Receipts")
    perm_payment_details = models.BooleanField(default=True, verbose_name="Payment Details")

    # System Administration
    perm_activity_logs = models.BooleanField(default=True, verbose_name="Activity Logs")
    perm_system_backup = models.BooleanField(default=True, verbose_name="System Backup")
    perm_employee_privileges = models.BooleanField(default=True, verbose_name="Employee Privileges")

    def __str__(self):
        return f"Privileges for {self.user.username}"