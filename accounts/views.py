from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from .forms import CustomLoginForm, CreateUserForm
from .models import UserProfile


def user_login(request):
    if request.user.is_authenticated:
        return redirect('performance:dashboard')

    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            remember_me = form.cleaned_data.get('remember_me')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                request.session.set_expiry(1209600 if remember_me else 0)
                next_url = request.GET.get('next')
                return redirect(next_url if next_url else 'performance:dashboard')
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomLoginForm()

    return render(request, 'accounts/login.html', {'form': form})


@login_required
def user_logout(request):
    username = request.user.username
    logout(request)
    messages.success(request, f'Goodbye {username}! You have been signed out.')
    return redirect('accounts:login')


@login_required
def user_management(request):
    if not request.user.is_superuser:
        messages.error(request, 'Access denied.')
        return redirect('performance:dashboard')

    users = User.objects.select_related('profile').all().order_by('-date_joined')
    role_counts = {}
    for choice_key, _ in UserProfile.ROLE_CHOICES:
        role_counts[choice_key] = UserProfile.objects.filter(role=choice_key).count()

    return render(request, 'accounts/user_management.html', {
        'users': users,
        'role_counts': role_counts,
        'total_users': users.count(),
    })


@login_required
def create_user(request):
    if not request.user.is_superuser:
        messages.error(request, 'Access denied.')
        return redirect('performance:dashboard')

    if request.method == 'POST':
        form = CreateUserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            role = form.cleaned_data['role']
            user.is_superuser = (role == 'system_admin')
            user.is_staff = (role in ('system_admin', 'teacher'))
            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.school_name = form.cleaned_data.get('school_name', '')
            profile.student_id_ref = form.cleaned_data.get('student_id_ref', '')
            profile.save()

            messages.success(request, f'User "{user.username}" created as {profile.get_role_display()}.')
            return redirect('accounts:users')
    else:
        form = CreateUserForm()

    return render(request, 'accounts/create_user.html', {'form': form})
