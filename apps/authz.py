"""
Role-based authorization helpers and object-level permission checks.

Roles are detected from the logged-in user's email matched against
the Student and Supervisor profile tables (same rule used by the
sidebar/dashboard routing).
"""
from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from apps.students.models import Student
from apps.supervisors.models import Supervisor


def _email(user):
    return (getattr(user, 'email', '') or '').strip()


def current_student(user):
    email = _email(user)
    if email:
        return Student.objects.filter(email__iexact=email).first()
    return None


def current_supervisor(user):
    email = _email(user)
    if email:
        return Supervisor.objects.filter(email__iexact=email).first()
    return None


def is_student(user):
    return bool(user and user.is_authenticated and user.groups.filter(name='student').exists())


def is_supervisor(user):
    return bool(user and user.is_authenticated and user.groups.filter(name='supervisor').exists())


def is_admin(user):
    """Admins are staff/superusers, or authenticated users with no student/supervisor profile."""
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return not is_student(user) and not is_supervisor(user)


def user_role(user):
    if is_admin(user):
        return 'admin'
    if is_supervisor(user):
        return 'supervisor'
    if is_student(user):
        return 'student'
    return 'guest'


def can_manage_placement(user, placement):
    """Admins manage any placement; supervisors can only manage their own."""
    if not user or not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    supervisor = current_supervisor(user)
    return bool(supervisor and placement.supervisor_id == supervisor.pk)


def can_view_placement(user, placement):
    """Admins, the assigned supervisor, and the placement's student may view it."""
    if not user or not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    supervisor = current_supervisor(user)
    if supervisor and placement.supervisor_id == supervisor.pk:
        return True
    student = current_student(user)
    return bool(student and placement.student_id == student.pk)


def get_placement_for_user(request, pk, manage=False):
    """Fetch a placement and enforce view or manage permission (403 otherwise)."""
    from django.shortcuts import get_object_or_404
    from apps.placements.models import Placement

    placement = get_object_or_404(Placement, pk=pk)
    allowed = can_manage_placement(request.user, placement) if manage else can_view_placement(request.user, placement)
    if not allowed:
        raise PermissionDenied('You do not have permission to access this placement.')
    return placement


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            return redirect('student_dashboard' if is_student(request.user) else 'supervisor_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
