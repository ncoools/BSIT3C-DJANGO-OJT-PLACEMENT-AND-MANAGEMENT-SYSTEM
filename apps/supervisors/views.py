from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import SupervisorForm
from .models import Supervisor


@login_required(login_url='login')
def supervisor_list(request):
    query = request.GET.get('q', '').strip()
    supervisors = Supervisor.objects.select_related('company', 'department')
    if query:
        supervisors = supervisors.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(contact_no__icontains=query)
            | Q(company__company_name__icontains=query)
            | Q(department__department_name__icontains=query)
        )
    return render(request, 'supervisors/supervisor_list.html', {
        'supervisors': supervisors,
        'query': query,
    })


@login_required(login_url='login')
def supervisor_create(request):
    form = SupervisorForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Supervisor created successfully.')
        return redirect('supervisors:list')
    return render(request, 'supervisors/supervisor_form.html', {
        'form': form,
        'title': 'Add supervisor',
    })


@login_required(login_url='login')
def supervisor_update(request, pk):
    supervisor = get_object_or_404(Supervisor, pk=pk)
    form = SupervisorForm(request.POST or None, instance=supervisor)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Supervisor updated successfully.')
        return redirect('supervisors:list')
    return render(request, 'supervisors/supervisor_form.html', {
        'form': form,
        'title': 'Edit supervisor',
        'supervisor': supervisor,
    })


@login_required(login_url='login')
@require_POST
def supervisor_delete(request, pk):
    supervisor = get_object_or_404(Supervisor, pk=pk)
    if supervisor.placements.exists():
        messages.error(request, 'This supervisor cannot be deleted while assigned to a placement.')
        return redirect('supervisors:list')
    supervisor.delete()
    messages.success(request, 'Supervisor deleted successfully.')
    return redirect('supervisors:list')
