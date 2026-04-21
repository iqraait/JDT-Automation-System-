from django.db import models
from django.conf import settings


class Institute(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='institute_profile'   # ✅ IMPORTANT FIX
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    address = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to='institute_logos/', blank=True, null=True)

    def __str__(self):
        return self.name


class AcademicYear(models.Model):
    institute = models.ForeignKey(
        Institute,
        on_delete=models.CASCADE,
        related_name='academic_years'
    )
    name = models.CharField(max_length=100)  # Example: 2025-2026
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"{self.name} - {self.institute.name}"