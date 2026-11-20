from datetime import date, time

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test import RequestFactory
from django.urls import reverse

from apps.companies.models import Company
from apps.students.models import Student
from apps.supervisors.models import Supervisor
from .forms import PlacementForm
from .models import Placement, PlacementEvaluation, PlacementRequirement, PlacementReport, Attendance
from .views import placement_list


class PlacementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tester', password='test-password', is_staff=True)
        self.client.force_login(self.user)
        self.student = Student.objects.create(
            student_number='2026-001',
            first_name='Jamie',
            last_name='Doe',
        )
        self.company = Company.objects.create(company_name='North Star')
        self.supervisor = Supervisor.objects.create(
            first_name='Alex',
            last_name='Smith',
            company=self.company,
        )

    def placement_data(self, **overrides):
        data = {
            'student': self.student.pk,
            'company': self.company.pk,
            'supervisor': self.supervisor.pk,
            'start_date': '2026-06-01',
            'end_date': '2026-09-01',
            'required_hours': 500,
        }
        data.update(overrides)
        return data

    def placement_list_response(self):
        request = RequestFactory().get(reverse('placements:list'))
        SessionMiddleware(lambda request: None).process_request(request)
        request.user = self.user
        request._messages = FallbackStorage(request)
        return placement_list(request)

    def test_create_placement_and_show_progress(self):
        response = self.client.post(reverse('placements:create'), self.placement_data())

        placement = Placement.objects.get()
        placement.completed_hours = 120
        placement.save()
        self.assertRedirects(response, reverse('placements:list'), fetch_redirect_response=False)
        self.assertEqual(placement.completed_hours, 120)
        self.assertContains(self.placement_list_response(), '120 / 500 hours')

    def test_reject_end_date_before_start_date(self):
        form = PlacementForm(
            data=self.placement_data(start_date='2026-09-01', end_date='2026-06-01')
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['end_date'], ['End date must be on or after the start date.'])

    def test_reject_completed_hours_above_required_hours(self):
        placement = Placement(
            student=self.student,
            company=self.company,
            supervisor=self.supervisor,
            start_date='2026-06-01',
            end_date='2026-09-01',
            required_hours=100,
            completed_hours=120,
        )
        with self.assertRaises(ValidationError):
            placement.clean()

    def test_delete_requires_post(self):
        placement = Placement.objects.create(
            student=self.student,
            company=self.company,
            supervisor=self.supervisor,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 9, 1),
            required_hours=500,
            completed_hours=120,
            status=Placement.Status.IN_PROGRESS,
        )

        response = self.client.get(reverse('placements:delete', args=[placement.pk]))

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Placement.objects.filter(pk=placement.pk).exists())


class PlacementPermissionTests(TestCase):
    """Admin-only placement assignment; supervisors still manage placement records."""

    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_user(username='admin', password='test-password', email='admin@example.com', is_staff=True)
        self.supervisor_user = User.objects.create_user(username='sup', password='test-password', email='sup@example.com')
        self.other_supervisor_user = User.objects.create_user(username='sup2', password='test-password', email='sup2@example.com')
        self.student_user = User.objects.create_user(username='stud', password='test-password', email='stud@example.com')

        self.company = Company.objects.create(company_name='North Star')
        self.supervisor = Supervisor.objects.create(
            first_name='Alex', last_name='Smith',
            company=self.company, email='sup@example.com',
        )
        self.other_supervisor = Supervisor.objects.create(
            first_name='Sam', last_name='Lee',
            company=self.company, email='sup2@example.com',
        )
        self.student = Student.objects.create(
            student_number='2026-001', first_name='Jamie', last_name='Doe',
            email='stud@example.com',
        )
        self.placement = Placement.objects.create(
            student=self.student, company=self.company, supervisor=self.supervisor,
            start_date=date(2026, 6, 1), end_date=date(2026, 9, 1),
            required_hours=500, status=Placement.Status.IN_PROGRESS,
        )
        # A different placement owned by the other supervisor
        other_student = Student.objects.create(
            student_number='2026-002', first_name='Jordan', last_name='Roe',
            email='jordan@example.com',
        )
        self.other_placement = Placement.objects.create(
            student=other_student, company=self.company, supervisor=self.other_supervisor,
            start_date=date(2026, 6, 1), end_date=date(2026, 9, 1),
            required_hours=500, status=Placement.Status.IN_PROGRESS,
        )

    def tearDown(self):
        pass

    def _login(self, user):
        self.client.force_login(user)

    def test_admin_can_edit_any_placement(self):
        self._login(self.admin_user)
        response = self.client.get(reverse('placements:update', args=[self.other_placement.pk]))
        self.assertEqual(response.status_code, 200)

    def test_supervisor_cannot_edit_placement(self):
        self._login(self.supervisor_user)
        response = self.client.get(reverse('placements:update', args=[self.placement.pk]))
        self.assertEqual(response.status_code, 403)

    def test_supervisor_cannot_delete_placement(self):
        self._login(self.supervisor_user)
        response = self.client.post(reverse('placements:delete', args=[self.placement.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Placement.objects.filter(pk=self.placement.pk).exists())

    def test_supervisor_cannot_create_placement_for_student(self):
        self._login(self.supervisor_user)
        response = self.client.post(reverse('placements:create'), {
            'student': self.student.pk,
            'company': self.company.pk,
            'supervisor': self.supervisor.pk,
            'start_date': '2026-06-01',
            'end_date': '2026-09-01',
            'required_hours': 500,
        })

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Placement.objects.filter(student=self.student).count(), 1)

    def test_admin_can_assign_student_to_a_different_supervisor(self):
        self._login(self.admin_user)
        response = self.client.post(reverse('placements:update', args=[self.placement.pk]), {
            'student': self.student.pk,
            'company': self.company.pk,
            'supervisor': self.other_supervisor.pk,
            'start_date': '2026-06-01',
            'end_date': '2026-09-01',
            'required_hours': 500,
        })

        self.assertRedirects(response, reverse('placements:list'), fetch_redirect_response=False)
        self.placement.refresh_from_db()
        self.assertEqual(self.placement.supervisor, self.other_supervisor)

    def test_supervisor_list_only_shows_their_placements(self):
        self._login(self.supervisor_user)
        response = self.client.get(reverse('placements:list'))
        self.assertContains(response, 'Jamie Doe')
        self.assertNotContains(response, 'Jordan Roe')

    def test_supervisor_list_hides_assignment_actions(self):
        self._login(self.supervisor_user)
        html = self.client.get(reverse('placements:list')).content.decode()

        self.assertNotIn('Add placement', html)
        self.assertNotIn(reverse('placements:create'), html)
        self.assertNotIn(reverse('placements:update', args=[self.placement.pk]), html)
        self.assertNotIn(reverse('placements:delete', args=[self.placement.pk]), html)

    def test_student_cannot_edit_placement(self):
        self._login(self.student_user)
        response = self.client.get(reverse('placements:update', args=[self.placement.pk]))
        self.assertEqual(response.status_code, 403)

    def test_student_can_view_own_placement_evaluations(self):
        self._login(self.student_user)
        response = self.client.get(reverse('placements:evaluation_list', args=[self.placement.pk]))
        self.assertEqual(response.status_code, 200)

    def test_student_cannot_view_other_students_evaluations(self):
        self._login(self.student_user)
        response = self.client.get(reverse('placements:evaluation_list', args=[self.other_placement.pk]))
        self.assertEqual(response.status_code, 403)

    def test_supervisor_profile_without_role_group_cannot_manage_placement(self):
        Group.objects.get_or_create(name='supervisor')[0].user_set.remove(self.supervisor_user)
        self._login(self.supervisor_user)

        response = self.client.get(reverse('placements:update', args=[self.placement.pk]))

        self.assertEqual(response.status_code, 403)

    def test_student_profile_without_role_group_cannot_view_placement(self):
        Group.objects.get_or_create(name='student')[0].user_set.remove(self.student_user)
        self._login(self.student_user)

        response = self.client.get(reverse('placements:evaluation_list', args=[self.placement.pk]))

        self.assertEqual(response.status_code, 403)

    def test_non_staff_without_role_cannot_manage_placement(self):
        user = get_user_model().objects.create_user(username='norole', password='test-password')
        self._login(user)

        response = self.client.get(reverse('placements:update', args=[self.placement.pk]))

        self.assertEqual(response.status_code, 403)

    def test_post_cannot_reparent_requirement_to_other_placement(self):
        self._login(self.supervisor_user)
        response = self.client.post(reverse('placements:requirement_create', args=[self.placement.pk]), {
            'placement': self.other_placement.pk,
            'requirement_name': 'Cross-placement attempt',
            'status': PlacementRequirement.Status.PENDING,
        })

        self.assertEqual(response.status_code, 302)
        requirement = PlacementRequirement.objects.get(requirement_name='Cross-placement attempt')
        self.assertEqual(requirement.placement_id, self.placement.pk)

    def test_post_cannot_reparent_evaluation_to_other_placement(self):
        self._login(self.supervisor_user)
        response = self.client.post(reverse('placements:evaluation_create', args=[self.placement.pk]), {
            'placement': self.other_placement.pk,
            'evaluator': self.supervisor.pk,
            'evaluation_date': date(2026, 7, 1),
            'rating': PlacementEvaluation.Rating.GOOD,
        })

        self.assertEqual(response.status_code, 302)
        evaluation = PlacementEvaluation.objects.get(evaluation_date=date(2026, 7, 1))
        self.assertEqual(evaluation.placement_id, self.placement.pk)
        self.assertEqual(evaluation.evaluator_id, self.supervisor.pk)

    def test_post_cannot_reparent_report_to_other_placement(self):
        self._login(self.supervisor_user)
        response = self.client.post(reverse('placements:report_create', args=[self.placement.pk]), {
            'placement': self.other_placement.pk,
            'report_type': PlacementReport.ReportType.WEEKLY,
            'report_date': date(2026, 7, 1),
            'content': 'Cross-placement attempt',
            'status': PlacementReport.Status.DRAFT,
        })

        self.assertEqual(response.status_code, 302)
        report = PlacementReport.objects.get(content='Cross-placement attempt')
        self.assertEqual(report.placement_id, self.placement.pk)


class AttendanceIntegrityTests(TestCase):
    """Audit trail + supervisor verification for attendance."""

    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_user(username='admin', password='test-password', email='admin@example.com', is_staff=True)
        self.supervisor_user = User.objects.create_user(username='sup', password='test-password', email='sup@example.com')
        self.student_user = User.objects.create_user(username='stud', password='test-password', email='stud@example.com')

        self.company = Company.objects.create(company_name='North Star')
        self.supervisor = Supervisor.objects.create(
            first_name='Alex', last_name='Smith',
            company=self.company, email='sup@example.com',
        )
        self.student = Student.objects.create(
            student_number='2026-001', first_name='Jamie', last_name='Doe',
            email='stud@example.com',
        )
        self.placement = Placement.objects.create(
            student=self.student, company=self.company, supervisor=self.supervisor,
            start_date=date(2026, 6, 1), end_date=date(2026, 9, 1),
            required_hours=500, status=Placement.Status.IN_PROGRESS,
        )
        self.record = Attendance.objects.create(
            placement=self.placement,
            attendance_date=date(2026, 6, 1),
            time_in=time(8, 0),
            time_out=time(17, 0),
        )

    def _login(self, user):
        self.client.force_login(user)

    def test_hours_auto_calculated_from_time_in_out(self):
        self.assertEqual(float(self.record.hours_rendered), 9.0)

    def test_update_requires_reason(self):
        self._login(self.admin_user)
        response = self.client.post(reverse('placements:attendance_update', args=[self.placement.pk, self.record.pk]), {
            'attendance_date': '2026-06-01',
            'time_in': '09:00',
            'time_out': '17:00',
            'status': 'Present',
        })
        self.assertEqual(response.status_code, 200)  # re-rendered with errors

    def test_update_writes_audit_log(self):
        from apps.placements.models import AttendanceEditLog

        self._login(self.admin_user)
        response = self.client.post(reverse('placements:attendance_update', args=[self.placement.pk, self.record.pk]), {
            'attendance_date': '2026-06-01',
            'time_in': '09:00',
            'time_out': '17:00',
            'status': 'Present',
            'reason': 'Corrected time-in',
        })
        self.assertRedirects(response, reverse('placements:attendance_list', args=[self.placement.pk]), fetch_redirect_response=False)
        log = AttendanceEditLog.objects.latest('created_at')
        self.assertIn('time_in: 08:00 → 09:00', log.changes)
        self.assertEqual(log.reason, 'Corrected time-in')
        self.assertEqual(log.editor, self.admin_user)

    def test_verify_requires_manage_permission(self):
        self._login(self.student_user)
        response = self.client.post(reverse('placements:attendance_verify', args=[self.placement.pk, self.record.pk]))
        self.assertEqual(response.status_code, 403)
        self.record.refresh_from_db()
        self.assertFalse(self.record.verified)

    def test_verify_sets_verified_flag(self):
        self._login(self.supervisor_user)
        response = self.client.post(reverse('placements:attendance_verify', args=[self.placement.pk, self.record.pk]))
        self.assertRedirects(response, reverse('placements:attendance_list', args=[self.placement.pk]), fetch_redirect_response=False)
        self.record.refresh_from_db()
        self.assertTrue(self.record.verified)


class PdfReportTests(TestCase):
    """PDF report generation."""

    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_user(username='admin', password='test-password', email='admin@example.com', is_staff=True)
        self.supervisor_user = User.objects.create_user(username='sup', password='test-password', email='sup@example.com')
        self.student_user = User.objects.create_user(username='stud', password='test-password', email='stud@example.com')

        self.company = Company.objects.create(company_name='North Star')
        self.supervisor = Supervisor.objects.create(
            first_name='Alex', last_name='Smith',
            company=self.company, email='sup@example.com',
        )
        self.student = Student.objects.create(
            student_number='2026-001', first_name='Jamie', last_name='Doe',
            email='stud@example.com',
        )
        self.placement = Placement.objects.create(
            student=self.student, company=self.company, supervisor=self.supervisor,
            start_date=date(2026, 6, 1), end_date=date(2026, 9, 1),
            required_hours=500, status=Placement.Status.IN_PROGRESS,
        )
        Attendance.objects.create(
            placement=self.placement, attendance_date=date(2026, 6, 1),
            time_in=time(8, 0), time_out=time(17, 0), verified=True,
        )

    def test_admin_can_download_report(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('placements:pdf_report', args=[self.placement.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn('attachment', response.get('Content-Disposition', ''))

    def test_student_can_download_own_report(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('placements:pdf_report', args=[self.placement.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/pdf')

    def test_supervisor_can_download_report(self):
        self.client.force_login(self.supervisor_user)
        response = self.client.get(reverse('placements:pdf_report', args=[self.placement.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_student_cannot_download_other_placements_report(self):
        other_student = Student.objects.create(
            student_number='2026-002', first_name='Jordan', last_name='Roe',
            email='jordan@example.com',
        )
        other_placement = Placement.objects.create(
            student=other_student, company=self.company, supervisor=self.supervisor,
            start_date=date(2026, 6, 1), end_date=date(2026, 9, 1),
            required_hours=500, status=Placement.Status.IN_PROGRESS,
        )
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('placements:pdf_report', args=[other_placement.pk]))

        self.assertEqual(response.status_code, 403)


class EvaluationAssignmentTests(TestCase):
    """Supervisor accounts get the evaluator field locked to themselves."""

    def setUp(self):
        User = get_user_model()
        self.supervisor_user = User.objects.create_user(username='sup', password='test-password', email='sup@example.com')
        self.other_supervisor_user = User.objects.create_user(username='sup2', password='test-password', email='sup2@example.com')

        self.company = Company.objects.create(company_name='North Star')
        self.supervisor = Supervisor.objects.create(
            first_name='Alex', last_name='Smith',
            company=self.company, email='sup@example.com',
        )
        self.other_supervisor = Supervisor.objects.create(
            first_name='Sam', last_name='Lee',
            company=self.company, email='sup2@example.com',
        )
        self.student = Student.objects.create(
            student_number='2026-001', first_name='Jamie', last_name='Doe',
            email='stud@example.com',
        )
        self.placement = Placement.objects.create(
            student=self.student, company=self.company, supervisor=self.supervisor,
            start_date=date(2026, 6, 1), end_date=date(2026, 9, 1),
            required_hours=500, status=Placement.Status.IN_PROGRESS,
        )

    def test_supervisor_evaluator_auto_set_to_self(self):
        self.client.force_login(self.supervisor_user)
        response = self.client.post(reverse('placements:evaluation_create', args=[self.placement.pk]), {
            'placement': self.placement.pk,
            'evaluator': self.other_supervisor.pk,  # should be ignored, locked to self
            'evaluation_date': '2026-06-10',
            'rating': 'excellent',
            'remarks': 'Good',
        })

        self.assertRedirects(response, reverse('placements:evaluation_list', args=[self.placement.pk]), fetch_redirect_response=False)
        evaluation = PlacementEvaluation.objects.get()
        self.assertEqual(evaluation.evaluator, self.supervisor)

    def test_supervisor_cannot_change_evaluator_via_post(self):
        self.client.force_login(self.supervisor_user)
        response = self.client.post(reverse('placements:evaluation_create', args=[self.placement.pk]), {
            'placement': self.placement.pk,
            'evaluator': self.other_supervisor.pk,
            'evaluation_date': '2026-06-10',
            'rating': 'good',
            'remarks': '',
        })

        evaluation = PlacementEvaluation.objects.get()
        self.assertEqual(evaluation.evaluator, self.supervisor)


