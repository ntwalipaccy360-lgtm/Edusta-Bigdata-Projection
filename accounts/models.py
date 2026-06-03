from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('system_admin', 'System Administrator'),
        ('school_admin', 'School Administrator'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    school_name = models.CharField(max_length=150, blank=True, default='Rwanda Ministry of Education')
    student_id_ref = models.CharField(
        max_length=30, blank=True, default='',
        help_text='Student record ID — required for student accounts'
    )

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f'{self.user.username} — {self.get_role_display()}'

    @property
    def role_badge_color(self):
        return {
            'system_admin': 'red',
            'school_admin': 'blue',
            'teacher': 'green',
            'student': 'purple',
        }.get(self.role, 'gray')

    @property
    def role_icon(self):
        return {
            'system_admin': '🔐',
            'school_admin': '🏫',
            'teacher': '📚',
            'student': '🎓',
        }.get(self.role, '👤')


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.is_superuser:
            role = 'system_admin'
        elif instance.is_staff:
            role = 'teacher'
        else:
            role = 'student'
        UserProfile.objects.get_or_create(user=instance, defaults={'role': role})
