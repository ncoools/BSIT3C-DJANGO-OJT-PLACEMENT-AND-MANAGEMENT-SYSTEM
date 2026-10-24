from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
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
        department = Department.objects.create(department_name='Information Technology')
        self.student = Student.objects.create(
            student_number='2026-001',
            first_name='Jamie',
            last_name='Doe',
            department=department,
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
            'completed_hours': 120,
            'status': Placement.Status.IN_PROGRESS,
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
        form = PlacementForm(
            data=self.placement_data(required_hours=100, completed_hours=120)
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['completed_hours'],
            ['Completed hours cannot exceed required hours.'],
        )

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
