from django.db import models

from apps.companies.models import Company
from apps.departments.models import Department


class Supervisor(models.Model):
    class Type(models.TextChoices):
        SCHOOL = 'School', 'School'
        COMPANY = 'Company', 'Company'

    supervisor_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    supervisor_type = models.CharField(max_length=7, choices=Type.choices)
    email = models.EmailField(max_length=100, blank=True, null=True)
    contact_no = models.CharField(max_length=20, blank=True, null=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='supervisors',
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='supervisors',
    )

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.supervisor_type})'
