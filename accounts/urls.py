"""
URL patterns for the Accounts app
Maps authentication URLs to views
"""

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('users/', views.user_management, name='users'),
    path('users/create/', views.create_user, name='create_user'),
]
