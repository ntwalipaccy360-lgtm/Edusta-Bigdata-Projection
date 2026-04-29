from django.urls import path
from . import views

app_name = 'performance'

urlpatterns = [
    path('', views.analytics_dashboard, name='dashboard'),
    path('risk-tracker/', views.risk_tracker, name='risk_tracker'),
    path('graduation/', views.graduation_analytics, name='graduation'),
    path('insights/', views.institutional_insights, name='insights'),
    path('management/', views.data_management, name='management'),
    path('bulk-upload/', views.upload_semester_data, name='bulk_upload'),
    path('submit-record/', views.submit_record, name='submit_record'),
    path('download-template/', views.download_template, name='download_template'),
    path('students/', views.student_list, name='student_list'),
    path('students/<str:student_id>/', views.student_profile, name='student_profile'),
    path('export/', views.export_students_csv, name='export_csv'),
]