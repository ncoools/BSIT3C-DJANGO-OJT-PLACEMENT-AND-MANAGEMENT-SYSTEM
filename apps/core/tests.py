from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.companies.models import Company
from apps.placements.models import Placement
from apps.students.models import Student
from apps.supervisors.models import Supervisor


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


class RoleGroupSyncTests(TestCase):
    """auth groups stay in sync with Student/Supervisor profile records."""

    def test_student_add_creates_group_membership(self):
        user = get_user_model().objects.create_user(username='stud', password='secret1234', email='stud@example.com')

        Student.objects.create(student_number='SYNC-001', first_name='Stu', last_name='Dent', email='stud@example.com')

        self.assertTrue(user.groups.filter(name='student').exists())

    def test_student_delete_removes_group_membership(self):
        user = get_user_model().objects.create_user(username='stud', password='secret1234', email='stud@example.com')

        student = Student.objects.create(student_number='SYNC-002', first_name='Stu', last_name='Dent', email='stud@example.com')
        student.delete()

        self.assertFalse(user.groups.filter(name='student').exists())

    def test_supervisor_add_creates_group_membership(self):
        user = get_user_model().objects.create_user(username='sup', password='secret1234', email='sup@example.com')

        Supervisor.objects.create(first_name='Sup', last_name='Visor', supervisor_type=Supervisor.Type.COMPANY, email='sup@example.com')

        self.assertTrue(user.groups.filter(name='supervisor').exists())

    def test_supervisor_delete_removes_group_membership(self):
        user = get_user_model().objects.create_user(username='sup', password='secret1234', email='sup@example.com')

        supervisor = Supervisor.objects.create(first_name='Sup', last_name='Visor', supervisor_type=Supervisor.Type.COMPANY, email='sup@example.com')
        supervisor.delete()

        self.assertFalse(user.groups.filter(name='supervisor').exists())


class RegistrationTests(TestCase):
    def test_register_student_creates_student_and_group(self):
        response = self.client.post(reverse('register'), {
            'username': 'newstudent',
            'first_name': 'New',
            'last_name': 'Student',
            'email': 'new@example.com',
            'password': 'secret-1234',
            'confirm_password': 'secret-1234',
            'student_number': '',
        })

        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)
        self.assertTrue(Student.objects.filter(email__iexact='new@example.com').exists())
        user = get_user_model().objects.get(username='newstudent')
        self.assertTrue(user.groups.filter(name='student').exists())

    def test_register_supervisor_creates_supervisor_and_group(self):
        response = self.client.post(reverse('supervisor_register'), {
            'first_name': 'Sup',
            'last_name': 'Visor',
            'email': 'supnew@example.com',
            'password': 'secret-1234',
            'confirm_password': 'secret-1234',
            'supervisor_type': Supervisor.Type.COMPANY,
        })

        self.assertRedirects(response, reverse('supervisor_dashboard'), fetch_redirect_response=False)
        self.assertTrue(Supervisor.objects.filter(email__iexact='supnew@example.com').exists())
        user = get_user_model().objects.get(username='supnew@example.com')
        self.assertTrue(user.groups.filter(name='supervisor').exists())


class AdminModuleAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username='admin', password='secret1234', email='admin@example.com')
        self.student_user = User.objects.create_user(username='stud', password='secret1234', email='stud@example.com')
        Student.objects.create(student_number='ACC-001', first_name='Stu', last_name='Dent', email='stud@example.com')
        self.supervisor_user = User.objects.create_user(username='sup', password='secret1234', email='sup@example.com')
        Supervisor.objects.create(first_name='Sup', last_name='Visor', supervisor_type=Supervisor.Type.COMPANY, email='sup@example.com')

    def test_student_redirected_from_students_module(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('students:list'))

        self.assertRedirects(response, reverse('student_dashboard'), fetch_redirect_response=False)

    def test_supervisor_redirected_from_supervisors_module(self):
        self.client.force_login(self.supervisor_user)
        response = self.client.get(reverse('supervisors:list'))

        self.assertRedirects(response, reverse('supervisor_dashboard'), fetch_redirect_response=False)

    def test_admin_can_access_students_module(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('students:list'))

        self.assertEqual(response.status_code, 200)

