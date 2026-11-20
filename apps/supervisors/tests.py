from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import TestCase
from django.test import RequestFactory
from django.urls import reverse

from apps.companies.models import Company
from apps.placements.models import Placement
from apps.students.models import Student
from .models import Supervisor
from .views import supervisor_list


class SupervisorModelTests(TestCase):
    def test_supervisor_can_reference_company(self):
        company = Company.objects.create(company_name='North Star')

        supervisor = Supervisor.objects.create(
            first_name='Alex',
            last_name='Smith',
            company=company,
        )

        self.assertEqual(supervisor.company, company)

    def test_company_is_optional(self):
        supervisor = Supervisor.objects.create(
            first_name='Jamie',
            last_name='Doe',
        )

        self.assertIsNone(supervisor.company)


class SupervisorViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tester', password='test-password', is_staff=True)
        self.client.force_login(self.user)
        self.company = Company.objects.create(company_name='North Star')

    def list_response(self, query=''):
        request = RequestFactory().get(reverse('supervisors:list'), {'q': query})
        SessionMiddleware(lambda request: None).process_request(request)
        request.user = self.user
        request._messages = FallbackStorage(request)
        return supervisor_list(request)

    def test_manual_supervisor_create_url_is_removed(self):
        response = self.client.get('/supervisors/add/')

        self.assertEqual(response.status_code, 404)

    def test_supervisor_list_has_no_manual_add_link(self):
        html = self.client.get(reverse('supervisors:list')).content.decode()

        self.assertNotIn('supervisors:create', html)
        self.assertNotIn('Add supervisor', html)

    def test_supervisor_assigned_to_placement_cannot_be_deleted(self):
        supervisor = Supervisor.objects.create(
            first_name='Alex',
            last_name='Smith',
            company=self.company,
        )
        student = Student.objects.create(
            student_number='2026-101',
            first_name='Jamie',
            last_name='Doe',
        )
        placement = Placement.objects.create(
            student=student,
            company=self.company,
            supervisor=supervisor,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 9, 1),
        )

        response = self.client.post(reverse('supervisors:delete', args=[supervisor.pk]))

        self.assertRedirects(response, reverse('supervisors:list'), fetch_redirect_response=False)
        self.assertTrue(Supervisor.objects.filter(pk=supervisor.pk).exists())
        self.assertTrue(Placement.objects.filter(pk=placement.pk).exists())
