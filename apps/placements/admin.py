from django.contrib import admin

from .models import Attendance, OJTSchedule, Placement
from .models import PlacementEvaluation, PlacementReport, PlacementRequirement


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


@admin.register(OJTSchedule)
class OJTScheduleAdmin(admin.ModelAdmin):
    list_display = ('placement', 'day_of_week', 'time_in', 'time_out')
    list_filter = ('day_of_week',)
    search_fields = ('placement__student__student_number', 'placement__company__company_name')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('placement', 'attendance_date', 'time_in', 'time_out', 'hours_rendered', 'status')
    list_filter = ('status', 'attendance_date')
    search_fields = ('placement__student__student_number', 'placement__company__company_name')


@admin.register(PlacementRequirement)
class PlacementRequirementAdmin(admin.ModelAdmin):
    list_display = ('placement', 'requirement_name', 'date_submitted', 'status')
    list_filter = ('status', 'placement')
    search_fields = ('placement__student__student_number', 'requirement_name')


@admin.register(PlacementEvaluation)
class PlacementEvaluationAdmin(admin.ModelAdmin):
    list_display = ('placement', 'evaluator', 'evaluation_date', 'score')
    list_filter = ('placement',)
    search_fields = ('placement__student__student_number',)


@admin.register(PlacementReport)
class PlacementReportAdmin(admin.ModelAdmin):
    list_display = ('placement', 'report_type', 'report_date', 'status')
    list_filter = ('status', 'report_type', 'placement')
    search_fields = ('placement__student__student_number',)
