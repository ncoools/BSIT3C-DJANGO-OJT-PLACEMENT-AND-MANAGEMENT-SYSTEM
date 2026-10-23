from django import forms

from .models import Student


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            'student_number',
            'first_name',
            'last_name',
            'email',
            'contact_no',
            'year_level',
            'department',
            'document',
        ]
        widgets = {
            'student_number': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_no': forms.TextInput(attrs={'class': 'form-control'}),
            'year_level': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'document': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
