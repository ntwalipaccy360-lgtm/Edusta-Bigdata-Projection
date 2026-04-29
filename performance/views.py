from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.generic import CreateView
from django.http import HttpResponse

from .models import AcademicRecord, Student, Course, Department
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


# ─── Role-based dashboard router ──────────────────────────────────────────────

@login_required
def analytics_dashboard(request):
    if request.user.is_superuser:
        return _admin_dashboard(request)
    elif request.user.is_staff:
        return _staff_dashboard(request)
    else:
        return _student_dashboard(request)


# ─── Admin dashboard ──────────────────────────────────────────────────────────

def _admin_dashboard(request):
    years = get_available_years()
    selected_year = get_selected_year(request)
    ctx = get_dashboard_context(selected_year)

    # Add department-level pass/fail breakdown for admin view
    dept_records = []
    for dept in Department.objects.all():
        records = AcademicRecord.objects.filter(
            academic_year=selected_year,
            student__department=dept
        )
        if records.exists():
            scores = [(r.ca_total or 0) + (r.mid_term or 0) + (r.final_exam or 0) for r in records]
            avg = sum(scores) / len(scores)
            passes = sum(1 for s in scores if s >= 50)
            dept_records.append({
                'name': dept.name,
                'code': dept.code,
                'total': len(scores),
                'passes': passes,
                'pass_rate': round(passes / len(scores) * 100, 1),
                'avg_score': round(avg, 1),
                'gpa': round(avg / 100 * 4.0, 2),
            })
    dept_records.sort(key=lambda x: x['pass_rate'], reverse=True)

    at_risk_total = AcademicRecord.objects.filter(
        academic_year=selected_year, ca_total__lt=20
    ).values('student').distinct().count()

    context = {
        'available_years': years,
        'selected_year': selected_year,
        'dept_records': dept_records,
        'at_risk_total': at_risk_total,
        **ctx,
    }
    return render(request, 'performance/overview.html', context)


# ─── Staff dashboard ──────────────────────────────────────────────────────────

def _staff_dashboard(request):
    selected_year = get_selected_year(request)
    years = get_available_years()
    dept_filter = request.GET.get('department', '')
    search = request.GET.get('search', '').strip()

    students_qs = Student.objects.all().select_related('department').order_by('last_name')
    if dept_filter:
        students_qs = students_qs.filter(department_id=dept_filter)
    if search:
        from django.db.models import Q as Qf
        students_qs = students_qs.filter(
            Qf(first_name__icontains=search) |
            Qf(last_name__icontains=search) |
            Qf(student_id__icontains=search)
        )

    student_data = []
    for student in students_qs:
        records = list(AcademicRecord.objects.filter(student=student, academic_year=selected_year))
        if records:
            ca_vals = [r.ca_total or 0 for r in records]
            totals = [(r.ca_total or 0) + (r.mid_term or 0) + (r.final_exam or 0) for r in records]
            att_vals = [r.attendance_rate or 0 for r in records if r.attendance_rate is not None]
            ca_avg = sum(ca_vals) / len(ca_vals)
            total_avg = sum(totals) / len(totals)
            att_avg = (sum(att_vals) / len(att_vals) * 100) if att_vals else 0
            passes = sum(1 for t in totals if t >= 50)
        else:
            ca_avg = total_avg = att_avg = passes = 0

        if ca_avg < 15:
            risk = 'critical'
        elif ca_avg < 20:
            risk = 'high'
        elif ca_avg < 25:
            risk = 'medium'
        else:
            risk = 'low'

        student_data.append({
            'student': student,
            'ca_avg': round(ca_avg, 1),
            'total_avg': round(total_avg, 1),
            'gpa': round(total_avg / 100 * 4.0, 2),
            'attendance': round(att_avg, 1),
            'risk': risk,
            'record_count': len(records),
            'passes': passes,
        })

    student_data.sort(key=lambda x: x['ca_avg'])

    critical = sum(1 for s in student_data if s['risk'] == 'critical')
    high = sum(1 for s in student_data if s['risk'] == 'high')
    medium = sum(1 for s in student_data if s['risk'] == 'medium')
    low = sum(1 for s in student_data if s['risk'] == 'low')

    # Subject performance
    subjects = {}
    for rec in AcademicRecord.objects.filter(academic_year=selected_year):
        code = rec.course_code
        total = (rec.ca_total or 0) + (rec.mid_term or 0) + (rec.final_exam or 0)
        if code not in subjects:
            subjects[code] = {'scores': [], 'name': code}
        subjects[code]['scores'].append(total)
    subject_list = [
        {
            'code': k,
            'name': v['name'],
            'avg': round(sum(v['scores']) / len(v['scores']), 1),
            'pass_rate': round(sum(1 for s in v['scores'] if s >= 50) / len(v['scores']) * 100, 1),
            'count': len(v['scores']),
        }
        for k, v in subjects.items()
    ]
    subject_list.sort(key=lambda x: x['avg'], reverse=True)

    context = {
        'available_years': years,
        'selected_year': selected_year,
        'student_data': student_data,
        'total_students': len(student_data),
        'critical_count': critical,
        'high_count': high,
        'medium_count': medium,
        'low_count': low,
        'at_risk_count': critical + high,
        'departments': Department.objects.all(),
        'dept_filter': dept_filter,
        'search': search,
        'subject_list': subject_list[:10],
    }
    return render(request, 'performance/staff_dashboard.html', context)


# ─── Student dashboard ────────────────────────────────────────────────────────

def _student_dashboard(request):
    selected_year = get_selected_year(request)
    years = get_available_years()

    # Try to link Django user → Student by username or name
    student = None
    try:
        student = (
            Student.objects.filter(student_id__iexact=request.user.username).first()
            or Student.objects.filter(
                first_name__iexact=request.user.first_name,
                last_name__iexact=request.user.last_name,
            ).first()
        )
    except Exception:
        pass

    if student:
        records = list(AcademicRecord.objects.filter(student=student, academic_year=selected_year))
        if records:
            ca_vals = [r.ca_total or 0 for r in records]
            totals = [(r.ca_total or 0) + (r.mid_term or 0) + (r.final_exam or 0) for r in records]
            att_vals = [r.attendance_rate or 0 for r in records if r.attendance_rate is not None]
            avg_ca = round(sum(ca_vals) / len(ca_vals), 1)
            avg_total = round(sum(totals) / len(totals), 1)
            avg_att = round((sum(att_vals) / len(att_vals) * 100) if att_vals else 0, 1)
            gpa = round(avg_total / 100 * 4.0, 2)

            if avg_ca >= 25 and avg_att >= 75:
                prediction, pred_color = 'Likely to Pass', 'green'
            elif avg_ca < 15 or avg_att < 60:
                prediction, pred_color = 'At Risk', 'red'
            else:
                prediction, pred_color = 'Borderline', 'yellow'

            course_data = []
            for r in records:
                total = (r.ca_total or 0) + (r.mid_term or 0) + (r.final_exam or 0)
                course_data.append({
                    'course': r.course_code,
                    'ca': r.ca_total or 0,
                    'midterm': r.mid_term or 0,
                    'final': r.final_exam or 0,
                    'total': round(total, 1),
                    'status': 'Pass' if total >= 50 else 'Fail',
                    'attendance': round((r.attendance_rate or 0) * 100, 1),
                })

            recs = []
            if avg_ca < 20:
                recs.append({'type': 'warning', 'icon': '⚠️', 'text': 'Your CA scores are below the threshold. Seek academic support immediately.'})
            if avg_att < 75:
                recs.append({'type': 'warning', 'icon': '📅', 'text': f'Attendance is {avg_att}% — below the required 75%. Please attend all scheduled classes.'})
            if avg_total >= 70:
                recs.append({'type': 'success', 'icon': '🏆', 'text': 'Excellent work! Consider academic leadership programmes or peer tutoring roles.'})
            elif avg_total >= 50:
                recs.append({'type': 'info', 'icon': '📚', 'text': 'You are on track. Focus on your weaker subjects to strengthen your overall grade.'})
            if not recs:
                recs.append({'type': 'info', 'icon': '💡', 'text': 'Stay consistent with your studies and maintain regular attendance.'})
        else:
            avg_ca = avg_total = avg_att = gpa = 0
            prediction, pred_color = 'No Records', 'gray'
            course_data = []
            recs = [{'type': 'info', 'icon': '📋', 'text': 'No academic records found for this year. Contact your department administrator.'}]
    else:
        avg_ca = avg_total = avg_att = gpa = 0
        prediction, pred_color = 'Not Linked', 'gray'
        course_data = []
        recs = [{'type': 'info', 'icon': '👤', 'text': 'Your student profile has not been linked. Contact your system administrator.'}]

    all_records = AcademicRecord.objects.filter(academic_year=selected_year)
    school_avg = 0
    if all_records.exists():
        all_scores = [(r.ca_total or 0) + (r.mid_term or 0) + (r.final_exam or 0) for r in all_records]
        school_avg = round(sum(all_scores) / len(all_scores), 1)

    context = {
        'available_years': years,
        'selected_year': selected_year,
        'student': student,
        'avg_ca': avg_ca,
        'avg_total': avg_total,
        'avg_att': avg_att,
        'gpa': gpa,
        'prediction': prediction,
        'pred_color': pred_color,
        'course_data': course_data,
        'recommendations': recs,
        'school_avg': school_avg,
    }
    return render(request, 'performance/student_dashboard.html', context)


# ─── Shared views ─────────────────────────────────────────────────────────────

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
            r.student.student_id, r.student.first_name, r.student.last_name,
            r.student.department.name, r.course_code,
            r.ca_total, r.mid_term, r.final_exam,
            round(total, 1), gpa, status, r.academic_year,
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
