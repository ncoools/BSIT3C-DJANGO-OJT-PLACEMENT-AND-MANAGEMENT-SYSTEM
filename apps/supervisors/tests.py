from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import TestCase
from django.test import RequestFactory
from django.urls import reverse

from apps.companies.models import Company
from apps.departments.models import Department
from apps.placements.models import Placement
from apps.students.models import Student
from .models import Supervisor
from .views import supervisor_list


class SupervisorModelTests(TestCase):
    def test_supervisor_can_reference_company_and_department(self):
        company = Company.objects.create(company_name='North Star')
        department = Department.objects.create(department_name='Information Technology')

        supervisor = Supervisor.objects.create(
            first_name='Alex',
            last_name='Smith',
            supervisor_type=Supervisor.Type.COMPANY,
            company=company,
            department=department,
        )

        self.assertEqual(supervisor.company, company)
        self.assertEqual(supervisor.department, department)

    def test_company_and_department_are_optional(self):
        supervisor = Supervisor.objects.create(
            first_name='Jamie',
            last_name='Doe',
            supervisor_type=Supervisor.Type.SCHOOL,
        )

        self.assertIsNone(supervisor.company)
        self.assertIsNone(supervisor.department)


class SupervisorViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tester', password='test-password')
        self.client.force_login(self.user)
        self.company = Company.objects.create(company_name='North Star')
        self.department = Department.objects.create(department_name='Information Technology')

    def list_response(self, query=''):
        request = RequestFactory().get(reverse('supervisors:list'), {'q': query})
        SessionMiddleware(lambda request: None).process_request(request)
        request.user = self.user
        request._messages = FallbackStorage(request)
        return supervisor_list(request)

    def test_create_supervisor(self):
        response = self.client.post(reverse('supervisors:create'), {
            'first_name': 'Alex',
            'last_name': 'Smith',
            'supervisor_type': Supervisor.Type.COMPANY,
            'email': 'alex@example.com',
            'contact_no': '555-0100',
            'company': self.company.pk,
            'department': self.department.pk,
        })

        supervisor = Supervisor.objects.get()
        self.assertRedirects(response, reverse('supervisors:list'), fetch_redirect_response=False)
        self.assertEqual(supervisor.company, self.company)
        self.assertContains(self.list_response('North Star'), 'Alex Smith')

    def test_supervisor_assigned_to_placement_cannot_be_deleted(self):
        supervisor = Supervisor.objects.create(
            first_name='Alex',
            last_name='Smith',
            supervisor_type=Supervisor.Type.COMPANY,
            company=self.company,
        )
        student = Student.objects.create(
            student_number='2026-101',
            first_name='Jamie',
            last_name='Doe',
            department=self.department,
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
