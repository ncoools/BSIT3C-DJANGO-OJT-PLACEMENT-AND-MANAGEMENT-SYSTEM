from datetime import date, time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.utils import timezone
from django.views.decorators.http import require_POST

from io import BytesIO

from xhtml2pdf import pisa

from .forms import (
    AttendanceForm,
    EvaluationForm,
    PlacementForm,
    ReportForm,
    RequirementForm,
)
from apps import authz

from .models import (
    Attendance,
    AttendanceEditLog,
    OJTSchedule,
    Placement,
    PlacementEvaluation,
    PlacementReport,
    PlacementRequirement,
)


def _log_attendance_change(attendance, editor, reason, old_values, creation=False):
    """Write an audit log entry for an attendance edit/create."""
    fields = ['attendance_date', 'time_in', 'time_out', 'time_in_pm', 'time_out_pm', 'status', 'hours_rendered', 'verified']
    if creation:
        changes = ', '.join(f'{field}={getattr(attendance, field)}' for field in fields if getattr(attendance, field) is not None)
    else:
        parts = []
        for field in fields:
            old = old_values.get(field)
            new = getattr(attendance, field)
            old_str = old.strftime('%H:%M') if isinstance(old, time) else str(old)
            new_str = new.strftime('%H:%M') if isinstance(new, time) else str(new)
            if old_str != new_str:
                parts.append(f'{field}: {old_str} → {new_str}')
        changes = ', '.join(parts) or 'no changes'
    AttendanceEditLog.objects.create(
        attendance=attendance,
        editor=editor if editor and editor.is_authenticated else None,
        reason=reason,
        changes=changes,
    )


@login_required(login_url='login')
def placement_list(request):
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    placements = Placement.objects.select_related('student', 'company', 'supervisor')
    if authz.is_admin(request.user):
        pass  # admins see all placements
    elif authz.is_supervisor(request.user):
        supervisor = authz.current_supervisor(request.user)
        placements = placements.filter(supervisor=supervisor)
    else:
        student = authz.current_student(request.user)
        placements = placements.filter(student=student)
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
        'is_admin': authz.is_admin(request.user),
    })


@login_required(login_url='login')
@authz.admin_only
def placement_create(request):
    form = PlacementForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Placement created successfully.')
        return redirect('placements:list')
    return render(request, 'placements/placement_form.html', {
        'form': form,
        'title': 'Add placement',
    })


@login_required(login_url='login')
@authz.admin_only
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
@authz.admin_only
@require_POST
def placement_delete(request, pk):
    placement = get_object_or_404(Placement, pk=pk)
    related_records_exist = (
        placement.evaluations.exists()
        or placement.requirements.exists()
        or placement.reports.exists()
        or placement.schedules.exists()
        or placement.attendance_records.exists()
    )
    if related_records_exist:
        messages.error(request, 'This placement cannot be deleted while related records exist.')
        return redirect('placements:list')
    placement.delete()
    messages.success(request, 'Placement deleted successfully.')
    return redirect('placements:list')


# PLACEMENT REQUIREMENTS
@login_required(login_url='login')
def placement_requirement_list(request, pk):
    placement = authz.get_placement_for_user(request, pk, manage=False)
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
    placement = authz.get_placement_for_user(request, pk, manage=True)
    form = RequirementForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        requirement = form.save(commit=False)
        requirement.placement = placement
        requirement.save()
        messages.success(request, 'Placement requirement created successfully.')
        return redirect('placements:requirement_list', pk=pk)
    return render(request, 'placements/placement_requirement_form.html', {
        'form': form,
        'title': 'Add placement requirement',
        'placement': placement,
    })


@login_required(login_url='login')
def placement_requirement_update(request, pk, requirement_pk):
    placement = authz.get_placement_for_user(request, pk, manage=True)
    requirement = get_object_or_404(PlacementRequirement, pk=requirement_pk, placement=placement)
    form = RequirementForm(request.POST or None, instance=requirement)
    if request.method == 'POST' and form.is_valid():
        requirement = form.save(commit=False)
        requirement.placement = placement
        requirement.save()
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
    placement = authz.get_placement_for_user(request, pk, manage=True)
    requirement = get_object_or_404(PlacementRequirement, pk=requirement_pk, placement=placement)
    requirement.delete()
    messages.success(request, 'Placement requirement deleted successfully.')
    return redirect('placements:requirement_list', pk=pk)


# PLACEMENT EVALUATIONS
@login_required(login_url='login')
def placement_evaluation_list(request, pk):
    placement = authz.get_placement_for_user(request, pk, manage=False)
    evaluations = placement.evaluations.all().order_by('-evaluation_date')
    return render(request, 'placements/placement_evaluation_list.html', {
        'placement': placement,
        'evaluations': evaluations,
    })


@login_required(login_url='login')
def placement_evaluation_create(request, pk):
    placement = authz.get_placement_for_user(request, pk, manage=True)
    supervisor = authz.current_supervisor(request.user)
    initial = {}
    if supervisor:
        initial['evaluator'] = supervisor
    form = EvaluationForm(request.POST or None, initial=initial)
    if supervisor:
        form.fields['evaluator'].disabled = True
        form.fields['evaluator'].help_text = 'Locked to your supervisor account.'
    if request.method == 'POST' and form.is_valid():
        evaluation = form.save(commit=False)
        evaluation.placement = placement
        if supervisor:
            evaluation.evaluator = supervisor
        evaluation.save()
        messages.success(request, 'Placement evaluation created successfully.')
        return redirect('placements:evaluation_list', pk=pk)
    return render(request, 'placements/placement_evaluation_form.html', {
        'form': form,
        'title': 'Add placement evaluation',
        'placement': placement,
    })


@login_required(login_url='login')
def placement_evaluation_update(request, pk, evaluation_pk):
    placement = authz.get_placement_for_user(request, pk, manage=True)
    evaluation = get_object_or_404(PlacementEvaluation, pk=evaluation_pk, placement=placement)
    supervisor = authz.current_supervisor(request.user)
    form = EvaluationForm(request.POST or None, instance=evaluation)
    if supervisor:
        form.fields['evaluator'].disabled = True
        form.fields['evaluator'].help_text = 'Locked to your supervisor account.'
    if request.method == 'POST' and form.is_valid():
        evaluation = form.save(commit=False)
        evaluation.placement = placement
        if supervisor:
            evaluation.evaluator = supervisor
        evaluation.save()
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
    placement = authz.get_placement_for_user(request, pk, manage=True)
    evaluation = get_object_or_404(PlacementEvaluation, pk=evaluation_pk, placement=placement)
    evaluation.delete()
    messages.success(request, 'Placement evaluation deleted successfully.')
    return redirect('placements:evaluation_list', pk=pk)


# PLACEMENT REPORTS
@login_required(login_url='login')
def placement_report_list(request, pk):
    placement = authz.get_placement_for_user(request, pk, manage=False)
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
    placement = authz.get_placement_for_user(request, pk, manage=True)
    form = ReportForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        report = form.save(commit=False)
        report.placement = placement
        report.save()
        messages.success(request, 'Placement report created successfully.')
        return redirect('placements:report_list', pk=pk)
    return render(request, 'placements/placement_report_form.html', {
        'form': form,
        'title': 'Add placement report',
        'placement': placement,
    })


@login_required(login_url='login')
def placement_report_update(request, pk, report_pk):
    placement = authz.get_placement_for_user(request, pk, manage=True)
    report = get_object_or_404(PlacementReport, pk=report_pk, placement=placement)
    form = ReportForm(request.POST or None, instance=report)
    if request.method == 'POST' and form.is_valid():
        report = form.save(commit=False)
        report.placement = placement
        report.save()
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
    placement = authz.get_placement_for_user(request, pk, manage=True)
    report = get_object_or_404(PlacementReport, pk=report_pk, placement=placement)
    report.delete()
    messages.success(request, 'Placement report deleted successfully.')
    return redirect('placements:report_list', pk=pk)


# PLACEMENT ATTENDANCE
@login_required(login_url='login')
def placement_attendance_list(request, pk):
    placement = authz.get_placement_for_user(request, pk, manage=False)
    from_date = request.GET.get('from_date', '').strip()
    to_date = request.GET.get('to_date', '').strip()

    records = placement.attendance_records.all().order_by('-attendance_date')
    if from_date:
        records = records.filter(attendance_date__gte=from_date)
    if to_date:
        records = records.filter(attendance_date__lte=to_date)
    attendance_records = list(records)

    rendered_hours = round(sum(float(r.hours_rendered or 0) for r in attendance_records if r.verified), 2)
    required_hours = placement.required_hours if placement.status != Placement.Status.CANCELLED else 0
    hours_pct = round((rendered_hours / required_hours * 100), 1) if required_hours else 0
    verified_count = sum(1 for r in attendance_records if r.verified)

    return render(request, 'placements/placement_attendance_list.html', {
        'placement': placement,
        'attendance_records': attendance_records,
        'rendered_hours': rendered_hours,
        'required_hours': required_hours,
        'hours_pct': hours_pct,
        'from_date': from_date,
        'to_date': to_date,
        'verified_count': verified_count,
    })


@login_required(login_url='login')
def placement_attendance_create(request, pk):
    placement = authz.get_placement_for_user(request, pk, manage=True)
    form = AttendanceForm(request.POST or None, initial={'placement': placement, 'attendance_date': date.today()})
    if request.method == 'POST' and form.is_valid():
        reason = form.cleaned_data['reason']
        attendance = form.save(commit=False)
        attendance.placement = placement
        attendance.save()
        _log_attendance_change(attendance, request.user, reason, {}, creation=True)
        messages.success(request, 'Attendance record added successfully.')
        return redirect('placements:attendance_list', pk=placement.pk)
    return render(request, 'placements/attendance_form.html', {
        'form': form,
        'title': 'Add attendance',
        'placement': placement,
    })


@login_required(login_url='login')
def placement_attendance_update(request, pk, attendance_pk):
    placement = authz.get_placement_for_user(request, pk, manage=True)
    attendance = get_object_or_404(Attendance, pk=attendance_pk, placement=placement)
    old_values = {
        'attendance_date': attendance.attendance_date,
        'time_in': attendance.time_in,
        'time_out': attendance.time_out,
        'time_in_pm': attendance.time_in_pm,
        'time_out_pm': attendance.time_out_pm,
        'status': attendance.status,
        'hours_rendered': attendance.hours_rendered,
        'verified': attendance.verified,
    }
    form = AttendanceForm(request.POST or None, instance=attendance)
    if request.method == 'POST' and form.is_valid():
        reason = form.cleaned_data['reason']
        attendance = form.save()  # hours_rendered auto-calculated on save
        _log_attendance_change(attendance, request.user, reason, old_values)
        messages.success(request, 'Attendance updated successfully.')
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url == 'supervisor_dashboard':
            return redirect('supervisor_dashboard')
        return redirect('placements:attendance_list', pk=placement.pk)
    return render(request, 'placements/attendance_form.html', {
        'form': form,
        'title': 'Edit attendance',
        'placement': placement,
        'attendance': attendance,
    })


@login_required(login_url='login')
@require_POST
def placement_attendance_delete(request, pk, attendance_pk):
    placement = authz.get_placement_for_user(request, pk, manage=True)
    attendance = get_object_or_404(Attendance, pk=attendance_pk, placement=placement)
    reason = request.POST.get('reason', 'Deleted by supervisor')
    _log_attendance_change(attendance, request.user, reason, {
        'attendance_date': attendance.attendance_date,
        'time_in': attendance.time_in,
        'time_out': attendance.time_out,
        'time_in_pm': attendance.time_in_pm,
        'time_out_pm': attendance.time_out_pm,
        'status': attendance.status,
        'hours_rendered': attendance.hours_rendered,
        'verified': attendance.verified,
    })
    attendance.delete()
    messages.success(request, 'Attendance record deleted successfully.')
    return redirect('placements:attendance_list', pk=placement.pk)


@login_required(login_url='login')
@require_POST
def placement_attendance_verify(request, pk, attendance_pk):
    """Supervisor verifies an attendance record. Only verified hours count toward OJT completion."""
    placement = authz.get_placement_for_user(request, pk, manage=True)
    attendance = get_object_or_404(Attendance, pk=attendance_pk, placement=placement)
    reason = request.POST.get('reason', 'Verified by supervisor')
    if not attendance.verified:
        old_values = {
            'attendance_date': attendance.attendance_date,
            'time_in': attendance.time_in,
            'time_out': attendance.time_out,
            'time_in_pm': attendance.time_in_pm,
            'time_out_pm': attendance.time_out_pm,
            'status': attendance.status,
            'hours_rendered': attendance.hours_rendered,
            'verified': attendance.verified,
        }
        attendance.verified = True
        attendance.save()
        _log_attendance_change(attendance, request.user, reason, old_values)
        messages.success(request, 'Attendance record verified.')
    else:
        messages.info(request, 'Record already verified.')
    from_url = request.POST.get('next')
    if from_url == 'supervisor_dashboard':
        return redirect('supervisor_dashboard')
    return redirect('placements:attendance_list', pk=placement.pk)


# PDF REPORT
def _render_pdf(template_name, context, filename):
    template = get_template(template_name)
    html = template.render(context)
    result = BytesIO()
    pdf = pisa.CreatePDF(BytesIO(html.encode('utf-8')), dest=result, encoding='utf-8')
    if pdf.err:
        return None
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required(login_url='login')
def placement_pdf_report(request, pk):
    placement = authz.get_placement_for_user(request, pk, manage=False)

    attendance = list(placement.attendance_records.all().order_by('attendance_date'))
    verified_hours = round(sum(float(r.hours_rendered or 0) for r in attendance if r.verified), 2)
    total_hours = round(sum(float(r.hours_rendered or 0) for r in attendance), 2)

    context = {
        'placement': placement,
        'attendance': attendance,
        'evaluations': placement.evaluations.select_related('evaluator').order_by('-evaluation_date'),
        'reports': placement.reports.all().order_by('-report_date'),
        'verified_hours': verified_hours,
        'total_hours': total_hours,
        'days_present': sum(1 for r in attendance if r.status == Attendance.Status.PRESENT),
        'days_absent': sum(1 for r in attendance if r.status == Attendance.Status.ABSENT),
        'days_late': sum(1 for r in attendance if r.status == Attendance.Status.LATE),
        'generated_at': timezone.now(),
    }
    filename = f'OJT_Placement_{placement.student.student_number}.pdf'
    response = _render_pdf('placements/placement_pdf_report.html', context, filename)
    if response is None:
        messages.error(request, 'Could not generate the PDF report.')
        return redirect('placements:list')
    return response
