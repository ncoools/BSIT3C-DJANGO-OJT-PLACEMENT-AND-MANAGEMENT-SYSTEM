from django.contrib import admin

from .models import Supervisor


@admin.register(Supervisor)
class SupervisorAdmin(admin.ModelAdmin):
    list_display = (
        'supervisor_id',
        'first_name',
        'last_name',
        'supervisor_type',
        'company',
        'department',
        'email',
    )
    list_filter = ('supervisor_type', 'company', 'department')
    search_fields = ('first_name', 'last_name', 'email', 'contact_no')
