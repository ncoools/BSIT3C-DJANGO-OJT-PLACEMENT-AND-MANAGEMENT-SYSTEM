from django import forms

from .models import Department


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['department_name', 'department_head']
        widgets = {
            'department_name': forms.TextInput(attrs={'class': 'form-control'}),
            'department_head': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_department_name(self):
        value = (self.cleaned_data.get('department_name') or '').strip()
        if value.upper() != 'INFORMATION TECHNOLOGY':
            raise forms.ValidationError('Only the Information Technology department is allowed.')
        return value
