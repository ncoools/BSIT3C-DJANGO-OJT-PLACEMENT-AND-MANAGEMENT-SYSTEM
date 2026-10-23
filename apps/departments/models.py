from django.db import models


class Department(models.Model):
    department_name = models.CharField(max_length=100, unique=True)
    department_head = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['department_name']

    def __str__(self):
        return self.department_name
