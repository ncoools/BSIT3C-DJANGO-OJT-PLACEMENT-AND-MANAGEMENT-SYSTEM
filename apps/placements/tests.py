from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test import RequestFactory
from django.urls import reverse

from apps.companies.models import Company
from apps.departments.models import Department
from apps.students.models import Student
from apps.supervisors.models import Supervisor
from .forms import PlacementForm
from .models import Placement
from .views import placement_list


class PlacementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tester', password='test-password')
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
            supervisor_type=Supervisor.Type.COMPANY,
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
    """Object-level permission checks: supervisors manage only their own placements."""

    def setUp(self):
        User = get_user_model()
        self.admin_user = User.objects.create_user(username='admin', password='test-password', email='admin@example.com')
        self.supervisor_user = User.objects.create_user(username='sup', password='test-password', email='sup@example.com')
        self.other_supervisor_user = User.objects.create_user(username='sup2', password='test-password', email='sup2@example.com')
        self.student_user = User.objects.create_user(username='stud', password='test-password', email='stud@example.com')

        department = Department.objects.create(department_name='Information Technology')
        self.company = Company.objects.create(company_name='North Star')
        self.supervisor = Supervisor.objects.create(
            first_name='Alex', last_name='Smith', supervisor_type=Supervisor.Type.COMPANY,
            company=self.company, email='sup@example.com',
        )
        self.other_supervisor = Supervisor.objects.create(
            first_name='Sam', last_name='Lee', supervisor_type=Supervisor.Type.COMPANY,
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

    def test_supervisor_can_edit_their_own_placement(self):
        self._login(self.supervisor_user)
        response = self.client.get(reverse('placements:update', args=[self.placement.pk]))
        self.assertEqual(response.status_code, 200)

    def test_supervisor_cannot_edit_other_supervisor_placement(self):
        self._login(self.supervisor_user)
        response = self.client.get(reverse('placements:update', args=[self.other_placement.pk]))
        self.assertEqual(response.status_code, 403)

    def test_supervisor_cannot_delete_other_supervisor_placement(self):
        self._login(self.supervisor_user)
        response = self.client.post(reverse('placements:delete', args=[self.other_placement.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Placement.objects.filter(pk=self.other_placement.pk).exists())

    def test_supervisor_list_only_shows_their_placements(self):
        self._login(self.supervisor_user)
        response = self.client.get(reverse('placements:list'))
        self.assertContains(response, 'Jamie Doe')
        self.assertNotContains(response, 'Jordan Roe')

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

