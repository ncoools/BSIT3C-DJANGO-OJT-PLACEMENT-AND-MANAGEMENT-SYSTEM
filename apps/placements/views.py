from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    EvaluationForm,
    PlacementForm,
    ReportForm,
    RequirementForm,
)
from .models import (
    Placement,
    PlacementEvaluation,
    PlacementReport,
    PlacementRequirement,
)


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


# PLACEMENT REQUIREMENTS
@login_required(login_url='login')
def placement_requirement_list(request, pk):
    placement = get_object_or_404(Placement, pk=pk)
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    requirements = placement.requirements.all().order_by('requirement_name')
    if query:
        requirements = requirements.filter(
            Q(requirement_name__icontains=query) | Q(status__icontains=query)
        )
    if status in PlacementRequirement.Status.values:
        requirements = requirements.filter(status=status)
    return render(request, 'placements/placement_requirement_list.html', {
        'placement': placement,
        'requirements': requirements,
        'query': query,
        'selected_status': status,
        'statuses': PlacementRequirement.Status.choices,
    })


@login_required(login_url='login')
def placement_requirement_create(request, pk):
    placement = get_object_or_404(Placement, pk=pk)
    form = RequirementForm(request.POST or None, initial={'placement': placement.pk})
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Placement requirement created successfully.')
        return redirect('placements:requirement_list', pk=pk)
    return render(request, 'placements/placement_requirement_form.html', {
        'form': form,
        'title': 'Add placement requirement',
        'placement': placement,
    })


@login_required(login_url='login')
def placement_requirement_update(request, pk, requirement_pk):
    placement = get_object_or_404(Placement, pk=pk)
    requirement = get_object_or_404(PlacementRequirement, pk=requirement_pk, placement=placement)
    form = RequirementForm(request.POST or None, instance=requirement)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Placement requirement updated successfully.')
        return redirect('placements:requirement_list', pk=pk)
    return render(request, 'placements/placement_requirement_form.html', {
        'form': form,
        'title': 'Edit placement requirement',
        'placement': placement,
        'requirement': requirement,
    })


@login_required(login_url='login')
@require_POST
def placement_requirement_delete(request, pk, requirement_pk):
    placement = get_object_or_404(Placement, pk=pk)
    requirement = get_object_or_404(PlacementRequirement, pk=requirement_pk, placement=placement)
    requirement.delete()
    messages.success(request, 'Placement requirement deleted successfully.')
    return redirect('placements:requirement_list', pk=pk)


# PLACEMENT EVALUATIONS
@login_required(login_url='login')
def placement_evaluation_list(request, pk):
    placement = get_object_or_404(Placement, pk=pk)
    evaluations = placement.evaluations.all().order_by('-evaluation_date')
    return render(request, 'placements/placement_evaluation_list.html', {
        'placement': placement,
        'evaluations': evaluations,
    })


@login_required(login_url='login')
def placement_evaluation_create(request, pk):
    placement = get_object_or_404(Placement, pk=pk)
    form = EvaluationForm(request.POST or None, initial={'placement': placement.pk})
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Placement evaluation created successfully.')
        return redirect('placements:evaluation_list', pk=pk)
    return render(request, 'placements/placement_evaluation_form.html', {
        'form': form,
        'title': 'Add placement evaluation',
        'placement': placement,
    })


@login_required(login_url='login')
def placement_evaluation_update(request, pk, evaluation_pk):
    placement = get_object_or_404(Placement, pk=pk)
    evaluation = get_object_or_404(PlacementEvaluation, pk=evaluation_pk, placement=placement)
    form = EvaluationForm(request.POST or None, instance=evaluation)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Placement evaluation updated successfully.')
        return redirect('placements:evaluation_list', pk=pk)
    return render(request, 'placements/placement_evaluation_form.html', {
        'form': form,
        'title': 'Edit placement evaluation',
        'placement': placement,
        'evaluation': evaluation,
    })


@login_required(login_url='login')
@require_POST
def placement_evaluation_delete(request, pk, evaluation_pk):
    placement = get_object_or_404(Placement, pk=pk)
    evaluation = get_object_or_404(PlacementEvaluation, pk=evaluation_pk, placement=placement)
    evaluation.delete()
    messages.success(request, 'Placement evaluation deleted successfully.')
    return redirect('placements:evaluation_list', pk=pk)


# PLACEMENT REPORTS
@login_required(login_url='login')
def placement_report_list(request, pk):
    placement = get_object_or_404(Placement, pk=pk)
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    reports = placement.reports.all().order_by('-report_date')
    if query:
        reports = reports.filter(Q(report_type__icontains=query) | Q(status__icontains=query))
    if status in PlacementReport.Status.values:
        reports = reports.filter(status=status)
    return render(request, 'placements/placement_report_list.html', {
        'placement': placement,
        'reports': reports,
        'query': query,
        'selected_status': status,
        'statuses': PlacementReport.Status.choices,
    })


@login_required(login_url='login')
def placement_report_create(request, pk):
    placement = get_object_or_404(Placement, pk=pk)
    form = ReportForm(request.POST or None, initial={'placement': placement.pk})
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Placement report created successfully.')
        return redirect('placements:report_list', pk=pk)
    return render(request, 'placements/placement_report_form.html', {
        'form': form,
        'title': 'Add placement report',
        'placement': placement,
    })


@login_required(login_url='login')
def placement_report_update(request, pk, report_pk):
    placement = get_object_or_404(Placement, pk=pk)
    report = get_object_or_404(PlacementReport, pk=report_pk, placement=placement)
    form = ReportForm(request.POST or None, instance=report)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Placement report updated successfully.')
        return redirect('placements:report_list', pk=pk)
    return render(request, 'placements/placement_report_form.html', {
        'form': form,
        'title': 'Edit placement report',
        'placement': placement,
        'report': report,
    })


@login_required(login_url='login')
@require_POST
def placement_report_delete(request, pk, report_pk):
    placement = get_object_or_404(Placement, pk=pk)
    report = get_object_or_404(PlacementReport, pk=report_pk, placement=placement)
    report.delete()
    messages.success(request, 'Placement report deleted successfully.')
    return redirect('placements:report_list', pk=pk)
