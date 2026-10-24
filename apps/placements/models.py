from django.core.exceptions import ValidationError
from django.db import models

from apps.companies.models import Company
from apps.students.models import Student
from apps.supervisors.models import Supervisor


class Placement(models.Model):
    class Status(models.TextChoices):
        PLANNED = 'planned', 'Planned'
        IN_PROGRESS = 'in_progress', 'In progress'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='placements')
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='placements')
    supervisor = models.ForeignKey(
        Supervisor,
        on_delete=models.PROTECT,
        related_name='placements',
        blank=True,
        null=True,
    )
    start_date = models.DateField()
    end_date = models.DateField()
    required_hours = models.PositiveIntegerField(default=500)
    completed_hours = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)

    class Meta:
        ordering = ['-start_date', 'student__last_name', 'student__first_name']

    def clean(self):
        super().clean()
        errors = {}
        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors['end_date'] = 'End date must be on or after the start date.'
        if self.completed_hours is not None and self.required_hours is not None:
            if self.completed_hours > self.required_hours:
                errors['completed_hours'] = 'Completed hours cannot exceed required hours.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.student} at {self.company}'
