from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class School(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_EXPIRED = 'expired'
    STATUS_SUSPENDED = 'suspended'

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=10, unique=True, help_text='Short code, e.g. GS, KIS, AUCA')
    district = models.CharField(max_length=100, blank=True, default='')
    province = models.CharField(max_length=100, blank=True, default='')
    school_admin = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_school'
    )
    subscription_start = models.DateField(null=True, blank=True)
    subscription_end = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    max_teachers = models.IntegerField(default=10)
    max_students = models.IntegerField(default=200)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    terminated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.code})'

    @property
    def subscription_is_expired(self):
        if self.subscription_end:
            return timezone.now().date() > self.subscription_end
        return False

    @property
    def subscription_status(self):
        if not self.is_active:
            return 'suspended'
        if self.subscription_is_expired:
            return 'expired'
        return 'active'

    @property
    def days_remaining(self):
        if self.subscription_end:
            delta = (self.subscription_end - timezone.now().date()).days
            return delta
        return None

    @property
    def is_accessible(self):
        return self.is_active and not self.subscription_is_expired

    def suspend(self):
        self.is_active = False
        self.terminated_at = timezone.now()
        self.save()

    def reactivate(self, new_end_date=None):
        self.is_active = True
        self.terminated_at = None
        if new_end_date:
            self.subscription_end = new_end_date
        self.save()


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('system_admin', 'System Administrator'),
        ('school_admin', 'School Administrator'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    school = models.ForeignKey(
        School, on_delete=models.SET_NULL, null=True, blank=True, related_name='members'
    )
    student_id_ref = models.CharField(
        max_length=30, blank=True, default='',
        help_text='Auto-generated student record ID'
    )

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f'{self.user.username} — {self.get_role_display()}'

    @property
    def school_name(self):
        if self.school:
            return self.school.name
        return 'Rwanda Ministry of Education'

    @property
    def subscription_blocked(self):
        if self.role in ('school_admin', 'teacher', 'student') and self.school:
            return not self.school.is_accessible
        return False

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


class KioskLookup(models.Model):
    student_id_searched = models.CharField(max_length=50)
    student = models.ForeignKey(
        'performance.Student', null=True, blank=True, on_delete=models.SET_NULL
    )
    school = models.ForeignKey(
        School, null=True, blank=True, on_delete=models.SET_NULL, related_name='kiosk_lookups'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    found = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        status = 'Found' if self.found else 'Not Found'
        return f'{self.student_id_searched} — {status} @ {self.timestamp:%Y-%m-%d %H:%M}'


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
