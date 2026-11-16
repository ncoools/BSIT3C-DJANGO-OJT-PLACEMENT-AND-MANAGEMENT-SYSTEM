from django.db import models

from apps.departments.models import Department


def student_document_path(instance, filename):
    return f'students/{instance.pk}/{filename}'


class Student(models.Model):
    student_number = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(max_length=100, blank=True)
    contact_no = models.CharField(max_length=20, blank=True)
    year_level = models.PositiveSmallIntegerField(null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='students')

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.student_number} - {self.first_name} {self.last_name}'
