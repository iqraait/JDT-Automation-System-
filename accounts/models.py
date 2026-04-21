from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('institute', 'Institute'),
    )

    role = models.CharField(max_length=50, choices=ROLE_CHOICES)

    # 🔥 LINK USER → INSTITUTE (IMPORTANT)
    institute = models.ForeignKey(
        'institutes.Institute',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )

    def __str__(self):
        return self.first_name if self.first_name else self.username