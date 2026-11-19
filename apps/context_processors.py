from apps import authz


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
    return {
        'is_student': authz.is_student(request.user),
        'is_supervisor': authz.is_supervisor(request.user),
        'is_admin': authz.is_admin(request.user),
        'user_role': authz.user_role(request.user),
    }


def student_context(request):
    """Expose whether the current user has a student profile (backward compat)."""
    return {'is_student': authz.is_student(request.user)}


def supervisor_context(request):
    """Expose whether the current user has a supervisor profile (backward compat)."""
    return {'is_supervisor': authz.is_supervisor(request.user)}
