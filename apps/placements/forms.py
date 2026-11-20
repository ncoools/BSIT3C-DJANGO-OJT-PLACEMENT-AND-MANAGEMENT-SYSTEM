from django import forms

from .models import Placement, PlacementEvaluation, PlacementReport, PlacementRequirement, Attendance


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
            'status',
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'company': forms.Select(attrs={'class': 'form-select'}),
            'supervisor': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'required_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supervisor'].help_text = (
            'Admin-only: the student will appear on this supervisor\'s dashboard.'
        )
        self.fields['status'].help_text = (
            'Set to "In progress" so the student can Time In and Time Out.'
        )


class RequirementForm(forms.ModelForm):
    class Meta:
        model = PlacementRequirement
        fields = ['requirement_name', 'date_submitted', 'file_path', 'status']
        widgets = {
            'requirement_name': forms.TextInput(attrs={'class': 'form-control'}),
            'date_submitted': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'file_path': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class EvaluationForm(forms.ModelForm):
    class Meta:
        model = PlacementEvaluation
        fields = ['evaluator', 'evaluation_date', 'rating', 'remarks']
        widgets = {
            'evaluator': forms.Select(attrs={'class': 'form-select'}),
            'evaluation_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'rating': forms.Select(attrs={'class': 'form-select'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control'}),
        }


class AttendanceForm(forms.ModelForm):
    reason = forms.CharField(
        required=True,
        label='Reason for correction',
        help_text='Explain why this attendance record is being changed (required for audit).',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Forgot to clock out, adjusted per supervisor'}),
    )

    class Meta:
        model = Attendance
        fields = ['attendance_date', 'time_in', 'time_out', 'status']
        widgets = {
            'attendance_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'time_in': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'time_out': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class ReportForm(forms.ModelForm):
    class Meta:
        model = PlacementReport
        fields = ['report_type', 'report_date', 'content', 'status']
        widgets = {
            'report_type': forms.Select(attrs={'class': 'form-select'}),
            'report_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'content': forms.Textarea(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
