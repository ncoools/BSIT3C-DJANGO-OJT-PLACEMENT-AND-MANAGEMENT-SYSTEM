from django.contrib import admin

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_number', 'first_name', 'last_name', 'department')
    list_filter = ('department',)
    search_fields = ('student_number', 'first_name', 'last_name', 'email')
