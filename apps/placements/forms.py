from django import forms

from .models import Placement


class PlacementForm(forms.ModelForm):
    class Meta:
        model = Placement
        fields = [
            'student',
            'company',
            'supervisor',
            'start_date',
            'end_date',
            'required_hours',
            'completed_hours',
            'status',
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'company': forms.Select(attrs={'class': 'form-select'}),
            'supervisor': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'required_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'completed_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
