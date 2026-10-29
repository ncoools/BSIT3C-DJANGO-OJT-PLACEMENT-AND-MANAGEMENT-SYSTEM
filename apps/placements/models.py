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


class OJTSchedule(models.Model):
    class DayOfWeek(models.TextChoices):
        MONDAY = 'Mon', 'Mon'
        TUESDAY = 'Tue', 'Tue'
        WEDNESDAY = 'Wed', 'Wed'
        THURSDAY = 'Thu', 'Thu'
        FRIDAY = 'Fri', 'Fri'
        SATURDAY = 'Sat', 'Sat'
        SUNDAY = 'Sun', 'Sun'

    schedule_id = models.AutoField(primary_key=True)
    placement = models.ForeignKey(Placement, on_delete=models.PROTECT, related_name='schedules')
    day_of_week = models.CharField(max_length=3, choices=DayOfWeek.choices)
    time_in = models.TimeField()
    time_out = models.TimeField()

    class Meta:
        db_table = 'ojt_schedules'

    def __str__(self):
        return f'{self.placement} - {self.day_of_week}'


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'Present', 'Present'
        ABSENT = 'Absent', 'Absent'
        LATE = 'Late', 'Late'
        EXCUSED = 'Excused', 'Excused'

    attendance_id = models.AutoField(primary_key=True)
    placement = models.ForeignKey(Placement, on_delete=models.PROTECT, related_name='attendance_records')
    attendance_date = models.DateField()
    time_in = models.TimeField(null=True, blank=True)
    time_out = models.TimeField(null=True, blank=True)
    hours_rendered = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=7, choices=Status.choices, default=Status.PRESENT)

    class Meta:
        db_table = 'attendance'

    def __str__(self):
        return f'{self.placement} - {self.attendance_date}'


class PlacementRequirement(models.Model):
    class Status(models.TextChoices):
        PENDING = 'Pending', 'Pending'
        SUBMITTED = 'Submitted', 'Submitted'
        APPROVED = 'Approved', 'Approved'
        REJECTED = 'Rejected', 'Rejected'

    requirement_id = models.AutoField(primary_key=True)
    placement = models.ForeignKey(Placement, on_delete=models.PROTECT, related_name='requirements')
    requirement_name = models.CharField(max_length=100)
    date_submitted = models.DateField(null=True, blank=True)
    file_path = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    class Meta:
        db_table = 'ojt_requirements'

    def __str__(self):
        return f'{self.placement} - {self.requirement_name}'


class PlacementEvaluation(models.Model):
    placement = models.ForeignKey(Placement, on_delete=models.PROTECT, related_name='evaluations')
    evaluator = models.ForeignKey(Supervisor, on_delete=models.PROTECT, related_name='evaluations')
    evaluation_date = models.DateField()
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'ojt_evaluations'

    def __str__(self):
        return f'{self.placement} - {self.evaluator}'


class PlacementReport(models.Model):
    class ReportType(models.TextChoices):
        WEEKLY = 'Weekly', 'Weekly'
        MONTHLY = 'Monthly', 'Monthly'
        FINAL = 'Final', 'Final'

    class Status(models.TextChoices):
        DRAFT = 'Draft', 'Draft'
        SUBMITTED = 'Submitted', 'Submitted'
        APPROVED = 'Approved', 'Approved'

    report_id = models.AutoField(primary_key=True)
    placement = models.ForeignKey(Placement, on_delete=models.PROTECT, related_name='reports')
    report_type = models.CharField(max_length=20, choices=ReportType.choices, default=ReportType.WEEKLY)
    report_date = models.DateField()
    content = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        db_table = 'ojt_reports'

    def __str__(self):
        return f'{self.placement} - {self.report_type}'
