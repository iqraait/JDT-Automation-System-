from django.db import models
from django.conf import settings


class Institute(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='institute_profile'   
        
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    address = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to='institute_logos/', blank=True, null=True)
    signature_image = models.ImageField(upload_to='institute_signatures/', blank=True, null=True, help_text="Signature for official documents like Allotment Memo")
    seal_image = models.ImageField(upload_to='institute_seals/', blank=True, null=True, help_text="Official seal for documents")

    def __str__(self):
        return self.name


class AcademicYear(models.Model):
    institute = models.ForeignKey(
        Institute,
        on_delete=models.CASCADE,
        related_name='academic_years'
    )
    name = models.CharField(max_length=100)  
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"{self.name} - {self.institute.name}"


class UserActivityLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activity_logs')
    institute = models.ForeignKey(Institute, on_delete=models.CASCADE, related_name='activity_logs', null=True, blank=True)
    module = models.CharField(max_length=100)
    activity = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
  


    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.module} - {self.activity[:30]} at {self.created_at}"


def log_activity(user, module, activity, institute=None):
    try:
        if user and user.is_authenticated:
            if not institute and hasattr(user, 'institute'):
                institute = user.institute
            UserActivityLog.objects.create(
                user=user,
                institute=institute,
                module=module,
                activity=activity
            )
    except Exception as e:
        print(f"Error logging activity: {str(e)}")
        