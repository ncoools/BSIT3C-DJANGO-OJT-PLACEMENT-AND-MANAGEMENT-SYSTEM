from django.test import TestCase

from apps.companies.models import Company
from apps.departments.models import Department
from .models import Supervisor


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
