"""
Views for the Accounts app
Handles user authentication (login/logout) and user management
"""

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from .forms import CustomLoginForm, CreateUserForm


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
                if not remember_me:
                    request.session.set_expiry(0)
                else:
                    request.session.set_expiry(1209600)
                messages.success(request, f'Welcome back, {user.username}!')
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('performance:dashboard')
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomLoginForm()

    return render(request, 'accounts/login.html', {'form': form, 'page_title': 'Login - AUCA'})


@login_required
def user_logout(request):
    username = request.user.username
    logout(request)
    messages.success(request, f'Goodbye {username}! You have been logged out successfully.')
    return redirect('accounts:login')


@login_required
def user_management(request):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access user management.')
        return redirect('performance:dashboard')
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'accounts/user_management.html', {'users': users})


@login_required
def create_user(request):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to create users.')
        return redirect('performance:dashboard')

    if request.method == 'POST':
        form = CreateUserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, f'User "{user.username}" created successfully.')
            return redirect('accounts:users')
    else:
        form = CreateUserForm()

    return render(request, 'accounts/create_user.html', {'form': form})
