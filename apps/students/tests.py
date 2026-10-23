import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.test import override_settings

from apps.departments.models import Department
from .models import Student


class StudentUploadTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.department = Department.objects.create(department_name='Information Technology')

    def test_student_upload_is_saved_in_student_id_folder(self):
        student = Student.objects.create(
            student_number='2026-001',
            first_name='Rendon',
            last_name='Nono',
            department=self.department,
            document=SimpleUploadedFile('record.txt', b'student file'),
        )

        expected_folder = Path(self.media_dir.name) / 'students' / str(student.pk)
        self.assertTrue(expected_folder.is_dir())
        self.assertEqual(Path(student.document.path).parent, expected_folder)
        self.assertTrue(Path(student.document.path).is_file())

    def test_student_create_view_accepts_file_upload(self):
        user = get_user_model().objects.create_user(username='tester', password='test-password')
        self.client.force_login(user)

        response = self.client.post(reverse('students:create'), {
            'student_number': '2026-002',
            'first_name': 'Jamie',
            'last_name': 'Doe',
            'email': 'jamie@example.com',
            'contact_no': '555-0100',
            'year_level': 3,
            'department': self.department.pk,
            'document': SimpleUploadedFile('proof.txt', b'uploaded proof'),
        })

        student = Student.objects.get(student_number='2026-002')
        self.assertRedirects(response, reverse('students:list'), fetch_redirect_response=False)
        self.assertTrue(Path(student.document.path).is_file())
