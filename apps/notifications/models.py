from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Category(models.TextChoices):
        PLACEMENT_ENDING = 'placement_ending', 'Placement ending soon'
        EVALUATION_DUE = 'evaluation_due', 'Evaluation due'
        UNPLACED_STUDENT = 'unplaced_student', 'Student not yet placed'
        UNVERIFIED_ATTENDANCE = 'unverified_attendance', 'Unverified attendance'
        SYSTEM = 'system', 'System'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.SYSTEM)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_category_display()} - {self.title}'
