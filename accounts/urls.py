from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # System admin: school admin accounts
    path('users/', views.user_management, name='users'),
    path('users/create/', views.create_user, name='create_user'),

    # System admin: school management
    path('schools/', views.school_list, name='school_list'),
    path('schools/new/', views.school_create, name='school_create'),
    path('schools/<int:pk>/edit/', views.school_edit, name='school_edit'),
    path('schools/<int:pk>/toggle/', views.school_toggle, name='school_toggle'),

    # School admin: their users
    path('my-school/', views.my_school_users, name='my_school_users'),
    path('my-school/add/', views.school_create_user, name='school_create_user'),

    # Subscription expired page
    path('subscription-expired/', views.subscription_expired, name='subscription_expired'),
]
