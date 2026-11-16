from django import forms

from apps.departments.models import Department

from .models import Supervisor


class SupervisorForm(forms.ModelForm):
    class Meta:
        model = Supervisor
        fields = [
            'first_name',
            'last_name',
            'supervisor_type',
            'email',
            'contact_no',
            'company',
            'department',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'supervisor_type': forms.Select(attrs={'class': 'form-select'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_no': forms.TextInput(attrs={'class': 'form-control'}),
            'company': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = Department.objects.filter(
            department_name__iexact='INFORMATION TECHNOLOGY'
        )
