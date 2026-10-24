from django.contrib import admin

from .models import Placement


@admin.register(Placement)
class PlacementAdmin(admin.ModelAdmin):
    list_display = ('student', 'company', 'supervisor', 'start_date', 'end_date', 'status')
    list_filter = ('status', 'company', 'start_date')
    search_fields = (
        'student__student_number',
        'student__first_name',
        'student__last_name',
        'company__company_name',
    )
