from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.utils import timezone
from .models import UserProfile, School

INPUT_CLASS = 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition'
SELECT_CLASS = INPUT_CLASS


class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Enter your username',
            'autocomplete': 'username',
        }),
        label='Username'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
        }),
        label='Password'
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'w-4 h-4 rounded'}),
        label='Keep me signed in'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.help_text = None


class SchoolForm(forms.ModelForm):
    """System admin creates/edits schools."""
    subscription_start = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
        label='Subscription Start'
    )
    subscription_end = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
        label='Subscription End (Due Date)'
    )

    class Meta:
        model = School
        fields = ['name', 'code', 'district', 'province', 'subscription_start', 'subscription_end',
                  'max_teachers', 'max_students', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'e.g. GS Kimironko'}),
            'code': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'e.g. GS, KIS, AUCA'}),
            'district': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'e.g. Gasabo'}),
            'province': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'e.g. Kigali City'}),
            'max_teachers': forms.NumberInput(attrs={'class': INPUT_CLASS}),
            'max_students': forms.NumberInput(attrs={'class': INPUT_CLASS}),
            'notes': forms.Textarea(attrs={
                'class': INPUT_CLASS, 'rows': 3, 'placeholder': 'Optional notes about this school...'
            }),
        }


class CreateSchoolAdminForm(forms.ModelForm):
    """System admin creates school admin accounts."""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Set a temporary password'}),
        label='Password'
    )
    school = forms.ModelChoiceField(
        queryset=School.objects.filter(school_admin__isnull=True),
        required=False,
        empty_label='— Assign to a school later —',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
        label='Assign to School'
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Last name'}),
            'username': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Login username'}),
            'email': forms.EmailInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Email address'}),
        }


class SchoolCreateUserForm(forms.ModelForm):
    """School admin creates teachers or students within their school."""
    ROLE_CHOICES_RESTRICTED = [
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    ]
    role = forms.ChoiceField(
        choices=ROLE_CHOICES_RESTRICTED,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
        label='Role'
    )
    department_code = forms.CharField(
        required=False,
        max_length=10,
        widget=forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'e.g. IT, CS, SE'}),
        label='Department Code',
        help_text='Used for student ID generation (students only)'
    )
    enrolment_year = forms.IntegerField(
        required=False,
        initial=timezone.now().year,
        widget=forms.NumberInput(attrs={'class': INPUT_CLASS, 'placeholder': str(timezone.now().year)}),
        label='Enrolment Year',
        help_text='Year the student enrolled — used in auto-generated ID'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Set a temporary password'}),
        label='Password'
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Last name'}),
            'username': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Login username'}),
            'email': forms.EmailInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Email address'}),
        }
