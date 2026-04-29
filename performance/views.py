from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.generic import CreateView
from django.http import HttpResponse

from .models import AcademicRecord, Student, Course
import csv
from .services.analytics import (
    get_available_years,
    get_selected_year,
    get_dashboard_context,
    get_risk_tracker_context,
    get_graduation_context,
    get_insights_context,
    get_student_list_context,
    get_student_profile_context,
    TARGET_YEAR,
)
from .services.data_import import import_records_from_file


@login_required
def analytics_dashboard(request):
    years = get_available_years()
    selected_year = get_selected_year(request)
    context = {
        'available_years': years,
        'selected_year': selected_year,
        **get_dashboard_context(selected_year),
    }
    return render(request, 'performance/overview.html', context)


@login_required
def risk_tracker(request):
    years = get_available_years()
    selected_year = get_selected_year(request)
    context = {
        'available_years': years,
        'selected_year': selected_year,
        **get_risk_tracker_context(request, selected_year),
    }
    return render(request, 'performance/risk_tracker.html', context)


@login_required
def graduation_analytics(request):
    years = get_available_years()
    selected_year = get_selected_year(request)
    context = {
        'available_years': years,
        'selected_year': selected_year,
        **get_graduation_context(selected_year),
    }
    return render(request, 'performance/graduation_analytics.html', context)


@login_required
def institutional_insights(request):
    years = get_available_years()
    selected_year = get_selected_year(request)
    context = {
        'available_years': years,
        'selected_year': selected_year,
        **get_insights_context(selected_year),
    }
    return render(request, 'performance/insights.html', context)


@login_required
def data_management(request):
    records = AcademicRecord.objects.filter(academic_year=TARGET_YEAR)
    total_samples = records.count()

    accuracy = 0
    if total_samples > 0:
        correct = sum(
            1 for r in records
            if ((r.ca_total or 0) >= 20 and (r.attendance_rate or 0) >= 0.7)
            == (((r.ca_total or 0) + (r.mid_term or 0) + (r.final_exam or 0)) >= 50)
        )
        accuracy = round((correct / total_samples) * 100, 1)

    context = {
        'total_samples': total_samples,
        'accuracy': accuracy,
        'ca_importance': 65,
        'attendance_importance': 35,
        'courses': Course.objects.all(),
        'csv_columns': [
            'student_id', 'first_name', 'last_name', 'department_code',
            'course_code', 'ca_total', 'final_exam', 'attendance_rate', 'academic_year'
        ],
    }
    return render(request, 'performance/ai_diagnostics.html', context)


@login_required
def upload_semester_data(request):
    if request.method == 'POST' and request.FILES.get('file'):
        success, message, _ = import_records_from_file(request.FILES['file'])
        if success:
            messages.success(request, message)
        else:
            messages.error(request, f'Error uploading data: {message}')
    return redirect('performance:management')


@login_required
def submit_record(request):
    if request.method == 'POST':
        try:
            student = Student.objects.get(student_id=request.POST.get('student_id'))
            AcademicRecord.objects.create(
                student=student,
                course_code=request.POST.get('course_code'),
                academic_year=TARGET_YEAR,
                ca_total=float(request.POST.get('ca_score', 0)),
                mid_term=0,
                final_exam=0,
                attendance_rate=float(request.POST.get('attendance', 0)),
                teacher_id='T001',
            )
            messages.success(request, f'Record added for {student.first_name} {student.last_name}')
        except Student.DoesNotExist:
            messages.error(request, f"Student ID {request.POST.get('student_id')} not found")
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    return redirect('performance:management')


@login_required
def student_list(request):
    years = get_available_years()
    selected_year = get_selected_year(request)
    context = {
        'available_years': years,
        'selected_year': selected_year,
        **get_student_list_context(request, selected_year),
    }
    return render(request, 'performance/student_list.html', context)


@login_required
def student_profile(request, student_id):
    years = get_available_years()
    selected_year = get_selected_year(request)
    profile_ctx = get_student_profile_context(student_id, selected_year)
    if profile_ctx is None:
        return render(request, 'performance/student_not_found.html', {'student_id': student_id})
    context = {
        'available_years': years,
        'selected_year': selected_year,
        **profile_ctx,
    }
    return render(request, 'performance/student_profile.html', context)


@login_required
def export_students_csv(request):
    selected_year = request.GET.get('academic_year', TARGET_YEAR)
    dept_filter = request.GET.get('department', '')
    search = request.GET.get('search', '').strip()

    records = AcademicRecord.objects.filter(
        academic_year=selected_year
    ).select_related('student', 'student__department')

    if dept_filter:
        records = records.filter(student__department_id=dept_filter)
    if search:
        from django.db.models import Q
        records = records.filter(
            Q(student__first_name__icontains=search) |
            Q(student__last_name__icontains=search) |
            Q(student__student_id__icontains=search)
        )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="edustat_export_{selected_year.replace("/","_")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Student ID', 'First Name', 'Last Name', 'Department', 'Course',
                     'CA Score', 'Mid Term', 'Final Exam', 'Total Score', 'GPA', 'Status', 'Academic Year'])

    for r in records:
        total = (r.ca_total or 0) + (r.mid_term or 0) + (r.final_exam or 0)
        gpa = round((total / 100) * 4.0, 2)
        status = 'Pass' if total >= 50 else 'Fail'
        writer.writerow([
            r.student.student_id,
            r.student.first_name,
            r.student.last_name,
            r.student.department.name,
            r.course_code,
            r.ca_total,
            r.mid_term,
            r.final_exam,
            round(total, 1),
            gpa,
            status,
            r.academic_year,
        ])

    return response


@login_required
def download_template(request):
    csv_content = (
        "student_id,first_name,last_name,department_code,department_name,"
        "course_code,ca_total,mid_term,final_exam,attendance_rate,academic_year\n"
        "2024001,John,Doe,CS,Computer Science,CS101,28.5,0,62,0.90,2025/2026\n"
        "2024002,Jane,Smith,BUS,Business Admin,BUS201,22.0,0,55,0.80,2025/2026\n"
        "2024003,Bob,Johnson,ENG,Engineering,ENG301,18.5,0,0,0.65,2025/2026\n"
    )
    response = HttpResponse(csv_content, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="edustat_template.csv"'
    return response


class RecordCreateView(CreateView):
    model = AcademicRecord
    fields = ['student', 'course_code', 'academic_year', 'ca_total', 'mid_term', 'final_exam', 'attendance_rate', 'teacher_id']
    template_name = 'performance/record_form.html'
    success_url = '/performance/'
