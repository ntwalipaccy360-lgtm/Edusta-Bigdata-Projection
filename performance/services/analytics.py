"""
Analytics Service
All business logic for dashboard, risk tracker, graduation, and insights views.
Views should call these functions and only handle HTTP request/response.
"""

import json
from django.db.models import Avg, Q
from django.db import models
from scipy.stats import pearsonr
from ..models import AcademicRecord, Department, Teacher, Course

TARGET_YEAR = "2025/2026"


def get_available_years():
    return AcademicRecord.objects.values_list(
        'academic_year', flat=True
    ).distinct().order_by('-academic_year')


def get_selected_year(request):
    years = get_available_years()
    return request.GET.get('academic_year') or (years[0] if years else TARGET_YEAR)


def get_dashboard_context(selected_year):
    records = AcademicRecord.objects.filter(
        academic_year=selected_year
    ).select_related('student', 'student__department')

    record_list = list(records)
    total_count = len(record_list)

    total_scores = [
        (r.ca_total or 0) + (r.mid_term or 0) + (r.final_exam or 0)
        for r in record_list
    ]
    avg_score = sum(total_scores) / len(total_scores) if total_scores else 0

    pass_count = sum(1 for s in total_scores if s >= 50)
    fail_count = total_count - pass_count
    pass_rate = round((pass_count / total_count) * 100, 1) if total_count else 0

    chart_data = [
        sum(1 for s in total_scores if s >= 80),
        sum(1 for s in total_scores if 70 <= s < 80),
        sum(1 for s in total_scores if 50 <= s < 70),
        sum(1 for s in total_scores if s < 50),
    ]

    alerts = records.filter(ca_total__lt=20).select_related(
        'student', 'student__department'
    )[:10]
    for alert in alerts:
        alert.ca_score = alert.ca_total
        total = (alert.ca_total or 0) + (alert.mid_term or 0) + (alert.final_exam or 0)
        alert.student_gpa = round((total / 100) * 4.0, 2)
        alert.risk_level = 'Critical' if (alert.ca_total or 0) < 15 else 'High'

    dept_stats = []
    for dept in Department.objects.all():
        dept_records = records.filter(student__department=dept)
        if dept_records.exists():
            dept_scores = [
                (r.ca_total or 0) + (r.mid_term or 0) + (r.final_exam or 0)
                for r in dept_records
            ]
            avg_dept = sum(dept_scores) / len(dept_scores)
            dept_pass = sum(1 for s in dept_scores if s >= 50)
            dept_stats.append({
                'code': dept.code,
                'name': dept.name,
                'avg_gpa': round((avg_dept / 100) * 4.0, 2),
                'avg_score': round(avg_dept, 1),
                'student_count': dept_records.count(),
                'pass_rate': round((dept_pass / len(dept_scores)) * 100, 1),
            })
    dept_stats.sort(key=lambda x: x['avg_gpa'], reverse=True)

    return {
        'total_count': total_count,
        'alert_count': records.filter(ca_total__lt=15).count(),
        'high_risk_count': records.filter(ca_total__lt=20).count(),
        'avg_gpa': round((avg_score / 100) * 4.0, 2),
        'avg_score': round(avg_score, 1),
        'pass_count': pass_count,
        'fail_count': fail_count,
        'pass_rate': pass_rate,
        'grad_ready_count': pass_count,
        'first_class_count': chart_data[0],
        'chart_data': chart_data,
        'dept_stats': dept_stats,
        'alerts': alerts,
    }


def get_student_list_context(request, selected_year):
    search = request.GET.get('search', '').strip()
    dept_filter = request.GET.get('department', '')
    risk_filter = request.GET.get('risk', '')

    records = AcademicRecord.objects.filter(
        academic_year=selected_year
    ).select_related('student', 'student__department')

    if search:
        records = records.filter(
            Q(student__first_name__icontains=search) |
            Q(student__last_name__icontains=search) |
            Q(student__student_id__icontains=search)
        )
    if dept_filter:
        records = records.filter(student__department_id=dept_filter)

    students_data = {}
    for r in records:
        sid = r.student.student_id
        if sid not in students_data:
            students_data[sid] = {
                'student': r.student,
                'records': [],
                'total_score': 0,
                'count': 0,
            }
        total = (r.ca_total or 0) + (r.mid_term or 0) + (r.final_exam or 0)
        students_data[sid]['records'].append(r)
        students_data[sid]['total_score'] += total
        students_data[sid]['count'] += 1

    student_rows = []
    for sid, data in students_data.items():
        avg_score = data['total_score'] / data['count'] if data['count'] else 0
        avg_ca = sum((r.ca_total or 0) for r in data['records']) / data['count'] if data['count'] else 0
        gpa = round((avg_score / 100) * 4.0, 2)
        is_at_risk = avg_ca < 15
        status = 'Critical' if avg_ca < 15 else ('High Risk' if avg_ca < 20 else ('Pass' if avg_score >= 50 else 'Fail'))
        student_rows.append({
            'student': data['student'],
            'avg_score': round(avg_score, 1),
            'avg_ca': round(avg_ca, 1),
            'gpa': gpa,
            'record_count': data['count'],
            'status': status,
            'is_at_risk': is_at_risk,
        })

    if risk_filter == 'at_risk':
        student_rows = [s for s in student_rows if s['is_at_risk']]
    elif risk_filter == 'pass':
        student_rows = [s for s in student_rows if not s['is_at_risk'] and s['avg_score'] >= 50]
    elif risk_filter == 'fail':
        student_rows = [s for s in student_rows if s['avg_score'] < 50 and not s['is_at_risk']]

    student_rows.sort(key=lambda x: x['avg_score'], reverse=True)

    return {
        'student_rows': student_rows,
        'departments': Department.objects.all(),
        'search': search,
        'selected_dept': dept_filter,
        'risk_filter': risk_filter,
        'total_count': len(student_rows),
    }


def get_student_profile_context(student_id, selected_year):
    from ..models import Student
    try:
        student = Student.objects.get(student_id=student_id)
    except Student.DoesNotExist:
        return None

    all_records = AcademicRecord.objects.filter(
        student=student
    ).select_related('student', 'student__department').order_by('academic_year', 'course_code')

    year_records = [r for r in all_records if r.academic_year == selected_year]

    records_data = []
    for r in all_records:
        total = (r.ca_total or 0) + (r.mid_term or 0) + (r.final_exam or 0)
        records_data.append({
            'record': r,
            'total': round(total, 1),
            'gpa': round((total / 100) * 4.0, 2),
            'status': 'Pass' if total >= 50 else 'Fail',
            'has_exam': (r.final_exam or 0) > 0,
        })

    total_scores = [(r.ca_total or 0) + (r.mid_term or 0) + (r.final_exam or 0) for r in all_records]
    avg_score = sum(total_scores) / len(total_scores) if total_scores else 0
    avg_ca = sum(r.ca_total or 0 for r in all_records) / len(all_records) if all_records else 0
    overall_gpa = round((avg_score / 100) * 4.0, 2)
    pass_count = sum(1 for s in total_scores if s >= 50)

    # Chart data - scores by course
    chart_labels = json.dumps([r['record'].course_code for r in records_data[:12]])
    chart_scores = json.dumps([r['total'] for r in records_data[:12]])
    chart_ca = json.dumps([r['record'].ca_total or 0 for r in records_data[:12]])

    is_at_risk = avg_ca < 15
    ml_prediction = 'Likely to Fail' if avg_score < 50 or avg_ca < 20 else 'Likely to Pass'

    return {
        'profile_student': student,
        'records_data': records_data,
        'total_records': len(records_data),
        'avg_score': round(avg_score, 1),
        'avg_ca': round(avg_ca, 1),
        'overall_gpa': overall_gpa,
        'pass_count': pass_count,
        'fail_count': len(records_data) - pass_count,
        'is_at_risk': is_at_risk,
        'ml_prediction': ml_prediction,
        'chart_labels': chart_labels,
        'chart_scores': chart_scores,
        'chart_ca': chart_ca,
    }


def get_risk_tracker_context(request, selected_year):
    records = AcademicRecord.objects.filter(
        academic_year=selected_year
    ).select_related('student', 'student__department')

    historical_avg = AcademicRecord.objects.exclude(
        academic_year=selected_year
    ).aggregate(Avg('ca_total'))['ca_total__avg'] or 0

    selected_dept = request.GET.get('department')
    if selected_dept:
        records = records.filter(student__department_id=selected_dept)

    for record in records:
        record.total_score = (
            (record.ca_total or 0) + (record.mid_term or 0) + (record.final_exam or 0)
        )
        if not record.final_exam or record.final_exam == 0:
            pre_exam = (record.ca_total or 0) + (record.mid_term or 0)
            record.status_label = "High Risk" if pre_exam < 30 else "On Track"
        else:
            record.status_label = "Cleared" if record.total_score >= 50 else "Failed"
        record.is_above_avg = record.ca_total > historical_avg

    return {
        'departments': Department.objects.all(),
        'alerts': records,
        'historical_baseline': round(historical_avg, 1),
        'stats': {
            'total': records.count(),
            'critical': records.filter(ca_total__lt=15).count(),
        },
    }


def get_graduation_context(selected_year):
    records = AcademicRecord.objects.filter(
        academic_year=selected_year
    ).select_related('student', 'student__department')

    total_scores_map = {}
    for r in records:
        total = (r.ca_total or 0) + (r.mid_term or 0) + (r.final_exam or 0)
        r.total_score = round(total, 1)
        total_scores_map[r.pk] = total

    graduation_ready = [r for r in records if total_scores_map[r.pk] >= 50]
    all_scores = list(total_scores_map.values())
    total = len(all_scores)

    first_class = sum(1 for s in all_scores if s >= 80)
    second_upper = sum(1 for s in all_scores if 70 <= s < 80)
    second_lower = sum(1 for s in all_scores if 50 <= s < 70)
    failing = sum(1 for s in all_scores if s < 50)

    grade_breakdown = [
        ('First Class (≥80)', first_class, 'bg-emerald-500'),
        ('Second Upper (70-79)', second_upper, 'bg-blue-500'),
        ('Second Lower (50-69)', second_lower, 'bg-yellow-500'),
        ('Failing (<50)', failing, 'bg-red-500'),
    ]

    # Department breakdown
    dept_labels = []
    dept_rates = []
    for dept in Department.objects.all():
        dept_records = [r for r in records if r.student.department_id == dept.pk]
        if dept_records:
            ready = sum(1 for r in dept_records if total_scores_map[r.pk] >= 50)
            dept_labels.append(dept.code)
            dept_rates.append(round(ready / len(dept_records) * 100, 1))

    return {
        'total_students': total,
        'graduation_ready': len(graduation_ready),
        'graduation_rate': round(len(graduation_ready) / total * 100, 1) if total else 0,
        'records': sorted(graduation_ready, key=lambda r: total_scores_map[r.pk], reverse=True),
        'grade_breakdown': grade_breakdown,
        'dept_labels': json.dumps(dept_labels),
        'dept_rates': json.dumps(dept_rates),
    }


def get_insights_context(selected_year):
    records = AcademicRecord.objects.filter(
        academic_year=selected_year
    ).select_related('student', 'student__department')

    # Department consistency matrix
    consistency_matrix = []
    for dept in Department.objects.all():
        dept_records = records.filter(student__department=dept)
        if not dept_records.exists():
            continue
        ca_scores = list(dept_records.values_list('ca_total', flat=True))
        final_scores = list(dept_records.values_list('final_exam', flat=True))
        try:
            correlation = round(pearsonr(ca_scores, final_scores)[0], 2) if len(ca_scores) > 1 else 0
        except Exception:
            correlation = 0
        avg_ca = sum(ca_scores) / len(ca_scores)
        avg_final = sum(final_scores) / len(final_scores)
        bias = "Lenient" if avg_ca > 25 and avg_final > 60 else ("Strict" if avg_ca < 20 and avg_final < 50 else "Balanced")
        consistency_matrix.append({
            'name': dept.name,
            'avg_ca': avg_ca,
            'avg_final': avg_final,
            'correlation': correlation,
            'bias': bias,
        })

    # Teacher recovery rates
    recovery_data = []
    for teacher in Teacher.objects.all()[:5]:
        teacher_records = records.filter(teacher_id=teacher.employee_id)
        low_ca = teacher_records.filter(ca_total__lt=20)
        if low_ca.exists():
            recovered = sum(
                1 for r in low_ca
                if (r.ca_total + r.mid_term + r.final_exam) >= 50
            )
            rate = round((recovered / low_ca.count()) * 100, 1)
        else:
            rate = 0
        recovery_data.append({'name': teacher.name, 'rate': rate})

    # Course performance chart
    course_data = {}
    for record in records:
        if record.course_code not in course_data:
            course_data[record.course_code] = {'scores': [], 'passed': 0, 'total': 0}
        total_score = (record.ca_total or 0) + (record.mid_term or 0) + (record.final_exam or 0)
        course_data[record.course_code]['scores'].append(total_score)
        course_data[record.course_code]['total'] += 1
        if total_score >= 50:
            course_data[record.course_code]['passed'] += 1

    chart_labels, chart_scores, chart_pass_rates = [], [], []
    for code, data in sorted(course_data.items())[:8]:
        chart_labels.append(code)
        chart_scores.append(round(sum(data['scores']) / len(data['scores']), 1))
        chart_pass_rates.append(round(data['passed'] / data['total'] * 100, 1) if data['total'] else 0)

    return {
        'consistency_matrix': consistency_matrix,
        'recovery_data': recovery_data,
        'chart_labels': json.dumps(chart_labels),
        'chart_scores': json.dumps(chart_scores),
        'chart_pass_rates': json.dumps(chart_pass_rates),
    }
