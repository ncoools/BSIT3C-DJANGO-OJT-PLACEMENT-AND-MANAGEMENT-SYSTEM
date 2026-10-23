import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Company


class CompanyUploadTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def test_company_upload_is_saved_in_company_name_folder(self):
        company = Company.objects.create(
            company_name='Acme Marine',
            document=SimpleUploadedFile('agreement.txt', b'company file'),
        )

        expected_folder = Path(self.media_dir.name) / 'companies' / 'acme-marine'
        self.assertTrue(expected_folder.is_dir())
        self.assertEqual(Path(company.document.path).parent, expected_folder)
        self.assertTrue(Path(company.document.path).is_file())

    def test_company_create_view_accepts_file_upload(self):
        user = get_user_model().objects.create_user(username='tester', password='test-password')
        self.client.force_login(user)

        response = self.client.post(reverse('companies:create'), {
            'company_name': 'North Star',
            'address': 'Main Street',
            'contact_person': 'Alex Smith',
            'contact_no': '555-0100',
            'email': 'alex@example.com',
            'document': SimpleUploadedFile('profile.txt', b'company profile'),
        })

        company = Company.objects.get(company_name='North Star')
        self.assertRedirects(response, reverse('companies:list'), fetch_redirect_response=False)
        self.assertTrue(Path(company.document.path).is_file())
