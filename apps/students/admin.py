from django.contrib import admin

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_number', 'first_name', 'last_name', 'department', 'year_level')
    list_filter = ('department', 'year_level')
    search_fields = ('student_number', 'first_name', 'last_name', 'email')
