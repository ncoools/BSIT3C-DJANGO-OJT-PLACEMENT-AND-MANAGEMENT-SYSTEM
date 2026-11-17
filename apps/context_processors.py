from apps.students.models import Student
from apps.supervisors.models import Supervisor


def placement_context(request):
    """Expose the most recent placement id for sidebar navigation."""
    first_placement_id = None
    try:
        from apps.placements.models import Placement

        first_placement = Placement.objects.order_by('-start_date').first()
        if first_placement is not None:
            first_placement_id = first_placement.pk
    except Exception:
        first_placement_id = None
    return {'first_placement_id': first_placement_id}


def user_role_context(request):
    """Expose the current user's role for sidebar navigation and access control."""
    is_student = False
    is_supervisor = False
    is_admin = False
    if request.user.is_authenticated:
        email = getattr(request.user, 'email', '') or ''
        if email:
            is_student = Student.objects.filter(email__iexact=email).exists()
            is_supervisor = Supervisor.objects.filter(email__iexact=email).exists()
            # Admin: staff user, or neither student nor supervisor
            is_admin = (
                request.user.is_staff
                or request.user.is_superuser
                or (not is_student and not is_supervisor)
            )
    return {
        'is_student': is_student,
        'is_supervisor': is_supervisor,
        'is_admin': is_admin,
        'user_role': 'admin' if is_admin else ('student' if is_student else ('supervisor' if is_supervisor else 'guest')),
    }


def student_context(request):
    """Expose whether the current user has a student profile (backward compat)."""
    return {'is_student': request.user.is_authenticated and Student.objects.filter(email__iexact=getattr(request.user, 'email', '') or '').exists()}


def supervisor_context(request):
    """Expose whether the current user has a supervisor profile (backward compat)."""
    return {'is_supervisor': request.user.is_authenticated and Supervisor.objects.filter(email__iexact=getattr(request.user, 'email', '') or '').exists()}
