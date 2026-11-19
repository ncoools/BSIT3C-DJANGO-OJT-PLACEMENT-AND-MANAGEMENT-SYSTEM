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
    is_admin = authz.is_admin(request.user)
    pending_approvals_count = 0
    if is_admin:
        try:
            from django.contrib.auth import get_user_model

            from apps.supervisors.models import Supervisor

            from django.db.models import Q

            pending_approvals_count = (
                get_user_model()
                .objects.filter(is_active=False)
                .filter(email__in=Supervisor.objects.values_list('email', flat=True))
                .count()
            )
        except Exception:
            pending_approvals_count = 0
    return {
        'is_student': authz.is_student(request.user),
        'is_supervisor': authz.is_supervisor(request.user),
        'is_admin': is_admin,
        'user_role': authz.user_role(request.user),
        'pending_approvals_count': pending_approvals_count,
    }


def student_context(request):
    """Expose whether the current user has a student profile (backward compat)."""
    return {'is_student': authz.is_student(request.user)}


def supervisor_context(request):
    """Expose whether the current user has a supervisor profile (backward compat)."""
    return {'is_supervisor': authz.is_supervisor(request.user)}
