from django.contrib import admin

from .models import Supervisor


@admin.register(Supervisor)
class SupervisorAdmin(admin.ModelAdmin):
    list_display = (
        'supervisor_id',
        'first_name',
        'last_name',
        'company',
        'email',
    )
    list_filter = ('company',)
    search_fields = ('first_name', 'last_name', 'email', 'contact_no')
