from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import PlacementForm
from .models import Placement


@login_required(login_url='login')
def placement_list(request):
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    placements = Placement.objects.select_related('student', 'company', 'supervisor')
    if query:
        placements = placements.filter(
            Q(student__student_number__icontains=query)
            | Q(student__first_name__icontains=query)
            | Q(student__last_name__icontains=query)
            | Q(company__company_name__icontains=query)
            | Q(supervisor__first_name__icontains=query)
            | Q(supervisor__last_name__icontains=query)
        )
    if status in Placement.Status.values:
        placements = placements.filter(status=status)
    return render(request, 'placements/placement_list.html', {
        'placements': placements,
        'query': query,
        'selected_status': status,
        'statuses': Placement.Status.choices,
    })


@login_required(login_url='login')
def placement_create(request):
    form = PlacementForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Placement created successfully.')
        return redirect('placements:list')
    return render(request, 'placements/placement_form.html', {'form': form, 'title': 'Add placement'})


@login_required(login_url='login')
def placement_update(request, pk):
    placement = get_object_or_404(Placement, pk=pk)
    form = PlacementForm(request.POST or None, instance=placement)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Placement updated successfully.')
        return redirect('placements:list')
    return render(request, 'placements/placement_form.html', {
        'form': form,
        'title': 'Edit placement',
        'placement': placement,
    })


@login_required(login_url='login')
@require_POST
def placement_delete(request, pk):
    placement = get_object_or_404(Placement, pk=pk)
    placement.delete()
    messages.success(request, 'Placement deleted successfully.')
    return redirect('placements:list')
