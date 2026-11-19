from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings

from apps.notifications.models import Notification
from apps.placements.models import Placement, PlacementEvaluation
from apps.students.models import Student


class Command(BaseCommand):
    help = 'Send OJT reminder notifications (in-app + email) to admins and supervisors'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=14,
            help='Consider placements ending within this many days (default: 14)',
        )

    def handle(self, *args, **options):
        days = options['days']
        today = date.today()
        horizon = today + timedelta(days=days)
        created = 0

        def notify(user, title, message, category, link=''):
            nonlocal created
            exists = Notification.objects.filter(
                user=user,
                title=title,
                category=category,
            ).exists()
            if exists:
                return
            Notification.objects.create(
                user=user,
                title=title,
                message=message,
                category=category,
                link=link,
            )
            created += 1

        def email_admins(subject, body):
            admins = get_user_model().objects.filter(is_staff=True, is_active=True).values_list('email', flat=True)
            admin_emails = [email for email in admins if email]
            if admin_emails:
                try:
                    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, admin_emails, fail_silently=False)
                except Exception:
                    self.stdout.write(self.style.WARNING('Email backend not configured; skipped sending emails.'))

        # 1. Placements ending within the horizon
        ending = Placement.objects.filter(
            status=Placement.Status.IN_PROGRESS,
            end_date__gte=today,
            end_date__lte=horizon,
        ).select_related('student', 'company', 'supervisor')

        admins = list(get_user_model().objects.filter(is_staff=True, is_active=True))

        for placement in ending:
            link = f'/placements/{placement.pk}/attendance/'
            supervisor_user = None
            if placement.supervisor and placement.supervisor.email:
                supervisor_user = get_user_model().objects.filter(email__iexact=placement.supervisor.email).first()

            if supervisor_user:
                notify(
                    supervisor_user,
                    f'Placement ending soon: {placement.student.first_name} {placement.student.last_name}',
                    f'Placement at {placement.company.company_name} ends on {placement.end_date:%B %d, %Y}. '
                    f'Hours rendered: {placement.completed_hours}/{placement.required_hours}.',
                    Notification.Category.PLACEMENT_ENDING,
                    link,
                )

            for admin in admins:
                notify(
                    admin,
                    f'Placement ending soon: {placement.student.first_name} {placement.student.last_name}',
                    f'{placement.student.first_name} {placement.student.last_name} at {placement.company.company_name} '
                    f'ends on {placement.end_date:%B %d, %Y}.',
                    Notification.Category.PLACEMENT_ENDING,
                    link,
                )

        # 2. Evaluations due: placements ending soon with no evaluation recorded
        ending_unevaluated = ending.exclude(
            pk__in=PlacementEvaluation.objects.values_list('placement_id', flat=True)
        )
        for placement in ending_unevaluated:
            link = f'/placements/{placement.pk}/evaluations/'
            supervisor_user = None
            if placement.supervisor and placement.supervisor.email:
                supervisor_user = get_user_model().objects.filter(email__iexact=placement.supervisor.email).first()

            if supervisor_user:
                notify(
                    supervisor_user,
                    f'Evaluation due: {placement.student.first_name} {placement.student.last_name}',
                    f'No evaluation recorded for {placement.student.first_name} {placement.student.last_name} '
                    f'at {placement.company.company_name}. Placement ends on {placement.end_date:%B %d, %Y}.',
                    Notification.Category.EVALUATION_DUE,
                    link,
                )

        # 3. Students not yet placed
        unplaced = Student.objects.filter(placements__isnull=True).distinct().count()
        if unplaced:
            for admin in admins:
                notify(
                    admin,
                    f'{unplaced} student(s) not yet placed',
                    f'{unplaced} student(s) currently have no OJT placement.',
                    Notification.Category.UNPLACED_STUDENT,
                    '/students/',
                )

        # 4. Unverified attendance records older than 1 day
        verification_cutoff = today - timedelta(days=1)
        unverified = Placement.objects.filter(
            status=Placement.Status.IN_PROGRESS,
            attendance_records__verified=False,
            attendance_records__attendance_date__lte=verification_cutoff,
        ).distinct().select_related('student', 'company', 'supervisor')

        for placement in unverified:
            link = f'/placements/{placement.pk}/attendance/'
            supervisor_user = None
            if placement.supervisor and placement.supervisor.email:
                supervisor_user = get_user_model().objects.filter(email__iexact=placement.supervisor.email).first()

            if supervisor_user:
                notify(
                    supervisor_user,
                    f'Unverified attendance: {placement.student.first_name} {placement.student.last_name}',
                    f'{placement.student.first_name} {placement.student.last_name} has unverified attendance records '
                    f'at {placement.company.company_name}. Please verify them.',
                    Notification.Category.UNVERIFIED_ATTENDANCE,
                    link,
                )

        # Email summary to admins
        if created:
            email_admins(
                'OJT placement reminders',
                f'{created} reminder notification(s) were generated. Please log in to review them.',
            )

        self.stdout.write(self.style.SUCCESS(f'Done. {created} notification(s) created.'))
