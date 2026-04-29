from .models import AcademicRecord
from .services.analytics import TARGET_YEAR


def global_stats(request):
    if not request.user.is_authenticated:
        return {}
    try:
        alert_count = AcademicRecord.objects.filter(
            academic_year=TARGET_YEAR,
            ca_total__lt=15
        ).count()
        return {'global_alert_count': alert_count}
    except Exception:
        return {'global_alert_count': 0}
