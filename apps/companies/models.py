from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils.text import slugify


def company_document_path(instance, filename):
    company_folder = slugify(instance.company_name) or 'company'
    return f'companies/{company_folder}/{filename}'


class Company(models.Model):
    company_name = models.CharField(max_length=150)
    address = models.CharField(max_length=255, blank=True)
    contact_person = models.CharField(max_length=100, blank=True)
    contact_no = models.CharField(max_length=20, blank=True)
    email = models.EmailField(max_length=100, blank=True)
    document = models.FileField(upload_to=company_document_path, blank=True)

    class Meta:
        ordering = ['company_name']

    def save(self, *args, **kwargs):
        pending_document = self.document if self.pk is None and self.document else None
        if pending_document:
            self.document = None
        try:
            super().save(*args, **kwargs)
        finally:
            if pending_document:
                self.document = pending_document

        company_folder = slugify(self.company_name) or 'company'
        (Path(settings.MEDIA_ROOT) / 'companies' / company_folder).mkdir(parents=True, exist_ok=True)
        if pending_document:
            self.save(update_fields=['document'])

    def __str__(self):
        return self.company_name
