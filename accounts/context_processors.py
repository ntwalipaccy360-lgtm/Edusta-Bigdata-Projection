def user_role(request):
    if not request.user.is_authenticated:
        return {'user_role': ''}
    if request.user.is_superuser:
        return {'user_role': 'system_admin'}
    try:
        return {'user_role': request.user.profile.role}
    except Exception:
        return {'user_role': 'teacher' if request.user.is_staff else 'student'}
