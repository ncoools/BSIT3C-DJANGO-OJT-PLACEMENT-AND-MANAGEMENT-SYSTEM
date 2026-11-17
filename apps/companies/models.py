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

    class Meta:
        ordering = ['company_name']

    def __str__(self):
        return self.company_name
