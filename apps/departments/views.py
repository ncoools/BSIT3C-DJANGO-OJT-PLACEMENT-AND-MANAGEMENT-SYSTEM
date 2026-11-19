from django.contrib import messages
from django.contrib.auth.decorators import login_required

from apps.authz import admin_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import DepartmentForm
from .models import Department


@admin_required
@login_required(login_url='login')
def department_list(request):
    departments = Department.objects.filter(department_name__iexact='INFORMATION TECHNOLOGY')
    return render(request, 'departments/department_list.html', {'departments': departments})


@admin_required
@login_required(login_url='login')
def department_create(request):
    form = DepartmentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Department created successfully.')
        return redirect('departments:list')
    return render(request, 'departments/department_form.html', {'form': form, 'title': 'Add department'})


@admin_required
@login_required(login_url='login')
def department_update(request, pk):
    department = get_object_or_404(Department, pk=pk)
    form = DepartmentForm(request.POST or None, instance=department)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Department updated successfully.')
        return redirect('departments:list')
    return render(request, 'departments/department_form.html', {
        'form': form,
        'title': 'Edit department',
        'department': department,
    })


@admin_required
@login_required(login_url='login')
@require_POST
def department_delete(request, pk):
    department = get_object_or_404(Department, pk=pk)
    department.delete()
    messages.success(request, 'Department deleted successfully.')
    return redirect('departments:list')
