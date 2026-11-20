"""Live, role-aware alerts shown on the PlaceIT dashboards."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from apps.placements.models import (
    Attendance,
    Placement,
    PlacementEvaluation,
    PlacementRequirement,
)
from apps.students.models import Student
from apps.supervisors.models import Supervisor

ENDING_DAYS = 14
VERIFICATION_LAG_DAYS = 1


def _alert(alert_id, severity, icon, count, title, message, link, link_label):
    return {
        'id': alert_id,
        'severity': severity,
        'icon': icon,
        'count': count,
        'title': title,
        'message': message,
        'link': link,
        'link_label': link_label,
    }


def _placement_link(url_name, placements, fallback='placements:list'):
    placement = placements.first()
    return reverse(url_name, args=[placement.pk]) if placement else reverse(fallback)


def _ending_placements(placements):
    today = timezone.localdate()
    return placements.filter(
        status=Placement.Status.IN_PROGRESS,
        end_date__gte=today,
        end_date__lte=today + timedelta(days=ENDING_DAYS),
    )


def admin_alerts():
    """Alerts for the OJT coordinator dashboard."""
    today = timezone.localdate()
    verification_cutoff = today - timedelta(days=VERIFICATION_LAG_DAYS)
    alerts = []

    unplaced = Student.objects.filter(placements__isnull=True).distinct().count()
    if unplaced:
        alerts.append(_alert(
            'unplaced-students', 'danger', 'fa-user', unplaced,
            'Students not yet placed',
            f'{unplaced} student{"s" if unplaced != 1 else ""} still need an OJT placement.',
            reverse('students:list'), 'Review students',
        ))

    pending_approvals = get_user_model().objects.filter(
        is_active=False,
        email__in=Supervisor.objects.values_list('email', flat=True),
    ).count()
    if pending_approvals:
        alerts.append(_alert(
            'pending-approvals', 'warning', 'fa-user-check', pending_approvals,
            'Supervisor approvals waiting',
            f'{pending_approvals} account{"s" if pending_approvals != 1 else ""} are waiting for approval.',
            reverse('approvals'), 'Review approvals',
        ))

    pending_requirements = PlacementRequirement.objects.filter(
        status=PlacementRequirement.Status.PENDING,
    ).count()
    if pending_requirements:
        alerts.append(_alert(
            'pending-requirements', 'warning', 'fa-file', pending_requirements,
            'Placement requirements pending',
            f'{pending_requirements} requirement{"s" if pending_requirements != 1 else ""} still need review.',
            reverse('placements:list'), 'Review placements',
        ))

    ending = _ending_placements(Placement.objects.all()).count()
    if ending:
        alerts.append(_alert(
            'placements-ending', 'info', 'fa-clock', ending,
            'Placements ending soon',
            f'{ending} active placement{"s" if ending != 1 else ""} end within {ENDING_DAYS} days.',
            reverse('placements:list'), 'Review placements',
        ))

    unverified = Attendance.objects.filter(
        verified=False,
        attendance_date__lte=verification_cutoff,
        placement__status=Placement.Status.IN_PROGRESS,
    ).count()
    if unverified:
        alerts.append(_alert(
            'unverified-attendance', 'danger', 'fa-check-circle', unverified,
            'Attendance needs verification',
            f'{unverified} attendance record{"s" if unverified != 1 else ""} are older than one day and still unverified.',
            reverse('placements:list'), 'Review attendance',
        ))

    return alerts


def student_alerts(student):
    """Alerts for the signed-in student's dashboard."""
    today = timezone.localdate()
    alerts = []

    pending_records = Attendance.objects.filter(
        placement__student=student,
        verified=False,
    ).select_related('placement')
    pending_count = pending_records.count()
    if pending_count:
        alerts.append(_alert(
            'attendance-awaiting-verification', 'warning', 'fa-check-circle', pending_count,
            'Attendance awaiting verification',
            f'{pending_count} record{"s" if pending_count != 1 else ""} are waiting for your supervisor.',
            _placement_link('placements:attendance_list', pending_records),
            'View attendance',
        ))

    pending_requirements = PlacementRequirement.objects.filter(
        placement__student=student,
        status=PlacementRequirement.Status.PENDING,
    ).select_related('placement')
    requirement_count = pending_requirements.count()
    if requirement_count:
        alerts.append(_alert(
            'requirements-to-submit', 'warning', 'fa-file', requirement_count,
            'Requirements to submit',
            f'{requirement_count} requirement{"s" if requirement_count != 1 else ""} still show as pending.',
            _placement_link('placements:requirement_list', pending_requirements),
            'View requirements',
        ))

    ending = _ending_placements(Placement.objects.filter(student=student)).count()
    if ending:
        alerts.append(_alert(
            'placement-ending', 'info', 'fa-clock', ending,
            'Placement ending soon',
            f'{ending} placement{"s" if ending != 1 else ""} end within {ENDING_DAYS} days.',
            reverse('student_dashboard'), 'View dashboard',
        ))

    return alerts


def supervisor_alerts(supervisor):
    """Alerts for the signed-in supervisor's dashboard."""
    today = timezone.localdate()
    verification_cutoff = today - timedelta(days=VERIFICATION_LAG_DAYS)
    placements = Placement.objects.filter(supervisor=supervisor)
    alerts = []

    unverified = Attendance.objects.filter(
        placement__in=placements,
        verified=False,
        attendance_date__lte=verification_cutoff,
    ).select_related('placement')
    unverified_count = unverified.count()
    if unverified_count:
        alerts.append(_alert(
            'unverified-attendance', 'danger', 'fa-check-circle', unverified_count,
            'Attendance needs verification',
            f'{unverified_count} record{"s" if unverified_count != 1 else ""} are waiting for your review.',
            _placement_link('placements:attendance_list', unverified),
            'Verify attendance',
        ))

    evaluated_ids = PlacementEvaluation.objects.filter(
        placement__in=placements,
    ).values_list('placement_id', flat=True)
    evaluations_due = _ending_placements(placements).exclude(pk__in=evaluated_ids)
    evaluation_count = evaluations_due.count()
    if evaluation_count:
        alerts.append(_alert(
            'evaluations-due', 'warning', 'fa-star', evaluation_count,
            'Evaluations due',
            f'{evaluation_count} placement{"s" if evaluation_count != 1 else ""} end soon without an evaluation.',
            _placement_link('placements:evaluation_list', evaluations_due),
            'Review evaluations',
        ))

    low_hours_count = _ending_placements(placements).filter(
        completed_hours__lt=F('required_hours'),
    ).count()
    if low_hours_count:
        alerts.append(_alert(
            'hours-behind', 'info', 'fa-hourglass-half', low_hours_count,
            'Hours may be behind',
            f'{low_hours_count} placement{"s" if low_hours_count != 1 else ""} end soon with hours still remaining.',
            reverse('placements:list'),
            'Review placements',
        ))

    return alerts
