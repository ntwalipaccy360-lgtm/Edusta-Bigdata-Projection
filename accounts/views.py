import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone

from .forms import CustomLoginForm, SchoolForm, CreateSchoolAdminForm, SchoolCreateUserForm
from .models import UserProfile, School, KioskLookup


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_role(user):
    if user.is_superuser:
        return 'system_admin'
    try:
        return user.profile.role
    except Exception:
        return 'teacher' if user.is_staff else 'student'


def _get_school(user):
    """Return the school associated with a user (via managed_school or profile.school)."""
    try:
        return user.managed_school
    except Exception:
        pass
    try:
        return user.profile.school
    except Exception:
        return None


def _generate_student_id(school, department_code, year):
    """
    Auto-generate student ID: {SCHOOL_CODE}{YY}{DEPT}{SEQ:03d}
    e.g. GS25IT047
    """
    from performance.models import Student
    year_short = str(year)[-2:]
    school_code = (school.code or 'SC')[:4].upper()
    dept_code = (department_code or 'XX')[:3].upper()
    prefix = f'{school_code}{year_short}{dept_code}'

    existing = Student.objects.filter(
        student_id__startswith=prefix
    ).order_by('student_id').values_list('student_id', flat=True)

    max_seq = 0
    for sid in existing:
        try:
            tail = sid[len(prefix):]
            m = re.search(r'\d+', tail)
            if m:
                max_seq = max(max_seq, int(m.group()))
        except Exception:
            pass

    # Also check UserProfile student_id_ref to avoid collision
    existing_refs = UserProfile.objects.filter(
        student_id_ref__startswith=prefix
    ).values_list('student_id_ref', flat=True)
    for sid in existing_refs:
        try:
            tail = sid[len(prefix):]
            m = re.search(r'\d+', tail)
            if m:
                max_seq = max(max_seq, int(m.group()))
        except Exception:
            pass

    return f'{prefix}{max_seq + 1:03d}'


# ─── Auth ─────────────────────────────────────────────────────────────────────

def user_login(request):
    if request.user.is_authenticated:
        return redirect('performance:dashboard')
    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data.get('username'),
                password=form.cleaned_data.get('password'),
            )
            if user is not None:
                login(request, user)
                request.session.set_expiry(1209600 if form.cleaned_data.get('remember_me') else 0)
                return redirect(request.GET.get('next') or 'performance:dashboard')
            messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomLoginForm()
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def user_logout(request):
    logout(request)
    return redirect('accounts:login')


# ─── System Admin: School Management ──────────────────────────────────────────

@login_required
def school_list(request):
    if _get_role(request.user) != 'system_admin':
        messages.error(request, 'Access denied.')
        return redirect('performance:dashboard')

    schools = School.objects.select_related('school_admin').all()

    # Auto-expire schools past their due date
    today = timezone.now().date()
    for school in schools:
        if school.is_active and school.subscription_end and school.subscription_end < today:
            school.is_active = False
            school.terminated_at = timezone.now()
            school.save(update_fields=['is_active', 'terminated_at'])

    # Compute expiry notifications
    expiring_soon = [
        s for s in schools
        if s.is_active and s.subscription_end
        and 0 <= (s.subscription_end - today).days <= 7
    ]
    expired = [s for s in schools if s.subscription_status == 'expired']
    suspended = [s for s in schools if s.subscription_status == 'suspended']

    return render(request, 'accounts/school_list.html', {
        'schools': schools,
        'expiring_soon': expiring_soon,
        'expired': expired,
        'suspended': suspended,
        'alert_count': len(expiring_soon) + len(expired),
    })


@login_required
def school_create(request):
    if _get_role(request.user) != 'system_admin':
        return redirect('performance:dashboard')
    if request.method == 'POST':
        form = SchoolForm(request.POST)
        if form.is_valid():
            school = form.save()
            messages.success(request, f'School "{school.name}" created.')
            return redirect('accounts:school_list')
    else:
        form = SchoolForm()
    return render(request, 'accounts/school_form.html', {'form': form, 'action': 'Create'})


@login_required
def school_edit(request, pk):
    if _get_role(request.user) != 'system_admin':
        return redirect('performance:dashboard')
    school = get_object_or_404(School, pk=pk)
    if request.method == 'POST':
        form = SchoolForm(request.POST, instance=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'School "{school.name}" updated.')
            return redirect('accounts:school_list')
    else:
        form = SchoolForm(instance=school)
    return render(request, 'accounts/school_form.html', {
        'form': form, 'school': school, 'action': 'Edit'
    })


@login_required
def school_toggle(request, pk):
    """Suspend or reactivate a school subscription."""
    if _get_role(request.user) != 'system_admin':
        return redirect('performance:dashboard')
    school = get_object_or_404(School, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'suspend':
            school.suspend()
            messages.warning(request, f'"{school.name}" subscription has been suspended.')
        elif action == 'reactivate':
            from datetime import date, timedelta
            new_end = request.POST.get('new_end')
            if new_end:
                from datetime import datetime
                end_date = datetime.strptime(new_end, '%Y-%m-%d').date()
            else:
                end_date = date.today() + timedelta(days=365)
            school.reactivate(end_date)
            messages.success(request, f'"{school.name}" reactivated until {end_date}.')
    return redirect('accounts:school_list')


# ─── System Admin: School Admin Accounts ──────────────────────────────────────

@login_required
def user_management(request):
    """System admin sees only school admin accounts."""
    if _get_role(request.user) != 'system_admin':
        messages.error(request, 'Access denied.')
        return redirect('performance:dashboard')

    school_admins = User.objects.filter(
        profile__role='school_admin'
    ).select_related('profile', 'managed_school').order_by('-date_joined')

    return render(request, 'accounts/user_management.html', {
        'users': school_admins,
        'total_users': school_admins.count(),
    })


@login_required
def create_user(request):
    """System admin creates school admin accounts only."""
    if _get_role(request.user) != 'system_admin':
        return redirect('performance:dashboard')

    if request.method == 'POST':
        form = CreateSchoolAdminForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.is_staff = True
            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = 'school_admin'
            school = form.cleaned_data.get('school')
            if school:
                profile.school = school
                school.school_admin = user
                school.save(update_fields=['school_admin'])
            profile.save()

            messages.success(request, f'School Admin "{user.username}" created.')
            return redirect('accounts:users')
    else:
        form = CreateSchoolAdminForm()
    return render(request, 'accounts/create_school_admin.html', {'form': form})


# ─── School Admin: Their Users ────────────────────────────────────────────────

@login_required
def my_school_users(request):
    """School admin sees and manages teachers & students in their school."""
    role = _get_role(request.user)
    if role != 'school_admin':
        return redirect('performance:dashboard')

    school = _get_school(request.user)
    if not school:
        messages.error(request, 'No school is linked to your account. Contact the system administrator.')
        return redirect('performance:dashboard')

    if not school.is_accessible:
        return redirect('accounts:subscription_expired')

    members = User.objects.filter(
        profile__school=school
    ).select_related('profile').exclude(pk=request.user.pk).order_by('profile__role', 'last_name')

    teacher_count = members.filter(profile__role='teacher').count()
    student_count = members.filter(profile__role='student').count()

    # Kiosk activity for this school
    kiosk_logs = KioskLookup.objects.filter(school=school).select_related('student')[:20]

    return render(request, 'accounts/my_school_users.html', {
        'school': school,
        'members': members,
        'teacher_count': teacher_count,
        'student_count': student_count,
        'kiosk_logs': kiosk_logs,
    })


@login_required
def school_create_user(request):
    """School admin creates a teacher or student in their school."""
    role = _get_role(request.user)
    if role != 'school_admin':
        return redirect('performance:dashboard')

    school = _get_school(request.user)
    if not school:
        messages.error(request, 'No school linked to your account.')
        return redirect('performance:dashboard')

    if not school.is_accessible:
        return redirect('accounts:subscription_expired')

    if request.method == 'POST':
        form = SchoolCreateUserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            new_role = form.cleaned_data['role']
            user.is_staff = (new_role == 'teacher')
            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = new_role
            profile.school = school

            if new_role == 'student':
                dept_code = form.cleaned_data.get('department_code', 'GEN')
                year = form.cleaned_data.get('enrolment_year') or timezone.now().year
                auto_id = _generate_student_id(school, dept_code, year)
                profile.student_id_ref = auto_id

            profile.save()

            messages.success(
                request,
                f'{"Teacher" if new_role == "teacher" else "Student"} "{user.username}" created'
                + (f' with ID {profile.student_id_ref}' if profile.student_id_ref else '') + '.'
            )
            return redirect('accounts:my_school_users')
    else:
        form = SchoolCreateUserForm()

    return render(request, 'accounts/school_create_user.html', {'form': form, 'school': school})


# ─── Subscription Expired ─────────────────────────────────────────────────────

@login_required
def subscription_expired(request):
    school = _get_school(request.user)
    return render(request, 'accounts/subscription_expired.html', {'school': school})
