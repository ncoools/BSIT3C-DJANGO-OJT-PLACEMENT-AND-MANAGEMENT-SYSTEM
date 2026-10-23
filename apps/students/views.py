from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import StudentForm
from .models import Student


@login_required(login_url='login')
def student_list(request):
    query = request.GET.get('q', '').strip()
    students = Student.objects.select_related('department')
    if query:
        students = students.filter(
            Q(student_number__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(department__department_name__icontains=query)
        )
    return render(request, 'students/student_list.html', {'students': students, 'query': query})


@login_required(login_url='login')
def student_create(request):
    form = StudentForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Student created successfully.')
        return redirect('students:list')
    return render(request, 'students/student_form.html', {'form': form, 'title': 'Add student'})


@login_required(login_url='login')
def student_update(request, pk):
    student = get_object_or_404(Student, pk=pk)
    form = StudentForm(request.POST or None, request.FILES or None, instance=student)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Student updated successfully.')
        return redirect('students:list')
    return render(request, 'students/student_form.html', {
        'form': form,
        'title': 'Edit student',
        'student': student,
    })


@login_required(login_url='login')
@require_POST
def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    student.delete()
    messages.success(request, 'Student deleted successfully.')
    return redirect('students:list')
