from django import forms

from .models import Placement, PlacementEvaluation, PlacementReport, PlacementRequirement


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


class RequirementForm(forms.ModelForm):
    class Meta:
        model = PlacementRequirement
        fields = ['placement', 'requirement_name', 'date_submitted', 'file_path', 'status']
        widgets = {
            'placement': forms.Select(attrs={'class': 'form-select'}),
            'requirement_name': forms.TextInput(attrs={'class': 'form-control'}),
            'date_submitted': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'file_path': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class EvaluationForm(forms.ModelForm):
    class Meta:
        model = PlacementEvaluation
        fields = ['placement', 'evaluator', 'evaluation_date', 'score', 'remarks']
        widgets = {
            'placement': forms.Select(attrs={'class': 'form-select'}),
            'evaluator': forms.Select(attrs={'class': 'form-select'}),
            'evaluation_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': '0.01'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control'}),
        }


class ReportForm(forms.ModelForm):
    class Meta:
        model = PlacementReport
        fields = ['placement', 'report_type', 'report_date', 'content', 'status']
        widgets = {
            'placement': forms.Select(attrs={'class': 'form-select'}),
            'report_type': forms.Select(attrs={'class': 'form-select'}),
            'report_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'content': forms.Textarea(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
