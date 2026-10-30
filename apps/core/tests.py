from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.companies.models import Company
from apps.departments.models import Department
from apps.placements.models import Placement, PlacementRequirement
from apps.students.models import Student


class HomeViewTests(TestCase):
    def test_home_renders_for_authenticated_user(self):
        user = get_user_model().objects.create_user(username='admin', password='secret1234')

        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_home_requires_login(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 302)

    def test_home_shows_live_placement_and_requirement_data(self):
        user = get_user_model().objects.create_user(username='coordinator', password='secret1234')
        self.client.force_login(user)
        department = Department.objects.create(department_name='Information Technology')
        student = Student.objects.create(
            student_number='2026-010',
            first_name='Jamie',
            last_name='Doe',
            department=department,
        )
        company = Company.objects.create(company_name='North Star')
        placement = Placement.objects.create(
            student=student,
            company=company,
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
            required_hours=500,
            completed_hours=125,
            status=Placement.Status.IN_PROGRESS,
        )
        PlacementRequirement.objects.create(
            placement=placement,
            requirement_name='Training agreement',
            status=PlacementRequirement.Status.SUBMITTED,
        )

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_students'], 1)
        self.assertEqual(response.context['currently_placed'], 1)
        self.assertEqual(response.context['unplaced'], 0)
        self.assertEqual(response.context['pending_requirements'], 1)
        self.assertContains(response, 'Jamie Doe')
        self.assertContains(response, 'Training agreement')
        self.assertContains(response, '125/500')
