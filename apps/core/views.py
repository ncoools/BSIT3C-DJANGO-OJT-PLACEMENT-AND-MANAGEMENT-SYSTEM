from datetime import date, datetime, timedelta

from apps import authz

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.authz import admin_required

from apps.companies.models import Company
from apps.placements.models import Placement, PlacementRequirement, PlacementEvaluation, Attendance
from apps.supervisors.models import Supervisor
from apps.students.models import Student

User = get_user_model()

MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION = timedelta(minutes=1)
INVALID_LOGIN_MESSAGE = 'Invalid username or password.'
LOCKED_MESSAGE = 'Too many failed attempts. Locked for 1 minute.'


def _reset_lock_state(request):
    request.session['failed_attempts'] = 0
    request.session['lock_time'] = None


def _get_lock_state(request):
    failed_attempts = request.session.get('failed_attempts', 0)
    lock_time = request.session.get('lock_time')

    if not lock_time:
        return failed_attempts, None

    try:
        unlock_time = timezone.datetime.fromisoformat(lock_time)
    except (TypeError, ValueError):
        _reset_lock_state(request)
        return 0, None

    if timezone.now() < unlock_time:
        remaining = int((unlock_time - timezone.now()).total_seconds())
        return failed_attempts, remaining

    _reset_lock_state(request)
    return 0, None


def _set_lock_state(request):
    lock_until = timezone.now() + LOCK_DURATION
    request.session['failed_attempts'] = MAX_FAILED_ATTEMPTS
    request.session['lock_time'] = lock_until.isoformat()
    return int(LOCK_DURATION.total_seconds())


def _validate_registration_data(data):
    errors = {}

    username = data.get('username', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip()

    if not username:
        errors['username'] = 'Username is required.'
    elif User.objects.filter(username=username).exists():
        errors['username'] = 'Username already taken.'

    if not first_name:
        errors['first_name'] = 'First name is required.'

    if not last_name:
        errors['last_name'] = 'Last name is required.'

    if not email:
        errors['email'] = 'Email is required.'
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors['email'] = 'Enter a valid email address.'
        else:
            if User.objects.filter(email=email).exists():
                errors['email'] = 'Email already registered.'

    # Students sign in with their student number as the password
    student_number = data.get('student_number', '').strip()

    if not student_number:
        errors['student_number'] = 'Student number is required (it becomes your password).'
    elif Student.objects.filter(student_number=student_number).exists():
        errors['student_number'] = 'Student number already taken.'

    return errors


def _validate_supervisor_registration_data(data):
    errors = {}
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    if not first_name:
        errors['first_name'] = 'First name is required.'

    if not last_name:
        errors['last_name'] = 'Last name is required.'

    if not email:
        errors['email'] = 'Email is required.'
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors['email'] = 'Enter a valid email address.'
        else:
            if User.objects.filter(email=email).exists() or Supervisor.objects.filter(email__iexact=email).exists():
                errors['email'] = 'Email already registered.'

    if not password:
        errors['password'] = 'Password is required.'
    elif len(password) < 8:
        errors['password'] = 'Password must be at least 8 characters.'
    else:
        try:
            validate_password(password)
        except ValidationError as exc:
            errors['password'] = ' '.join(exc.messages)

    if password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match.'

    supervisor_type = data.get('supervisor_type', Supervisor.Type.COMPANY)
    if supervisor_type not in Supervisor.Type.values:
        errors['supervisor_type'] = 'Select a valid supervisor type.'

    return errors


@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    failed_attempts, remaining = _get_lock_state(request)
    if remaining is not None:
        messages.error(request, f'Too many failed attempts. Try again in {remaining} seconds.')
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    if request.method == 'GET':
        return render(request, 'auth/login.html')

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    user = authenticate(request, username=username, password=password)

    if user is not None:
        _reset_lock_state(request)
        login(request, user)
        return redirect('dashboard')

    # Surface a clear message when the account exists but is still pending approval
    pending_user = User.objects.filter(is_active=False).filter(
        username__iexact=username,
    ).first() or User.objects.filter(is_active=False, email__iexact=username).first()
    if pending_user:
        _reset_lock_state(request)
        messages.info(request, 'Your account is pending administrator approval. You will be notified once it is approved.')
        return render(request, 'auth/login.html')

    failed_attempts += 1
    request.session['failed_attempts'] = failed_attempts
    if failed_attempts >= MAX_FAILED_ATTEMPTS:
        remaining = _set_lock_state(request)
        messages.error(request, LOCKED_MESSAGE)
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    remaining_attempts = MAX_FAILED_ATTEMPTS - failed_attempts
    messages.error(request, f'{INVALID_LOGIN_MESSAGE} {remaining_attempts} attempts remaining.')
    return render(request, 'auth/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required(login_url='login')
def home(request):
    role = authz.user_role(request.user)
    if role == 'student':
        return redirect('student_dashboard')
    if role == 'supervisor':
        return redirect('supervisor_dashboard')
    if role != 'admin':
        raise PermissionDenied('Your account has no assigned role. Please contact an administrator.')

    total_students = Student.objects.count()
    partner_companies = Company.objects.count()
    total_placements = Placement.objects.count()
    active_placements = Placement.objects.filter(status=Placement.Status.IN_PROGRESS).count()
    completed_placements = Placement.objects.filter(status=Placement.Status.COMPLETED).count()
    pending_requirements = PlacementRequirement.objects.filter(status=PlacementRequirement.Status.PENDING).count()
    unplaced_students = Student.objects.filter(placements__isnull=True).distinct().count()

    recent_placements = list(
        Placement.objects
        .select_related('student', 'company', 'supervisor')
        .order_by('-start_date')
        .all()
    )

    pending_requirements_list = list(
        PlacementRequirement.objects
        .filter(status=PlacementRequirement.Status.PENDING)
        .select_related('placement__student')
        .order_by('date_submitted', 'placement__student__last_name', 'placement__student__first_name')
    )

    status_rows = [
        ('Ongoing', Placement.Status.IN_PROGRESS, '#D4AF37'),
        ('Completed', Placement.Status.COMPLETED, '#16a34a'),
        ('Pending', Placement.Status.PLANNED, '#D97706'),
        ('Dropped', Placement.Status.CANCELLED, '#dc2626'),
    ]
    from apps.notifications.models import Notification
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()
    recent_notifications = list(
        Notification.objects.filter(user=request.user).order_by('-created_at')[:10].values(
            'id', 'title', 'message', 'category', 'link', 'is_read',
        )
    )
    status_segments = []
    total_status = sum(Placement.objects.filter(status=status).count() for _, status, _ in status_rows)
    running_offset = 0
    for label, status, color in status_rows:
        value = Placement.objects.filter(status=status).count()
        pct = (value / total_status * 100) if total_status else 0
        status_segments.append({
            'label': label,
            'value': value,
            'color': color,
            'dasharray': f'{pct:.1f} {100 - pct:.1f}',
            'offset': -running_offset,
        })
        running_offset += pct

    # --- Analytics ---
    placements_by_month = list(
        Placement.objects
        .annotate(month=TruncMonth('start_date'))
        .values('month')
        .annotate(count=Count('pk'))
        .order_by('month')
    )
    month_labels = [entry['month'].strftime('%b %Y') if entry['month'] else '—' for entry in placements_by_month]
    month_data = [entry['count'] for entry in placements_by_month]

    students_per_company = list(
        Company.objects
        .annotate(student_count=Count('placements__student', distinct=True))
        .order_by('-student_count')[:5]
        .values('company_name', 'student_count')
    )
    company_names = [entry['company_name'] for entry in students_per_company]
    company_data = [entry['student_count'] for entry in students_per_company]

    total_rendered_hours = float(
        Attendance.objects.aggregate(total=Sum('hours_rendered'))['total'] or 0
    )
    total_required_hours = Placement.objects.aggregate(total=Sum('required_hours'))['total'] or 0

    context = {
        'total_students': total_students,
        'partner_companies': partner_companies,
        'total_placements': total_placements,
        'active_placements': active_placements,
        'completed_placements': completed_placements,
        'pending_requirements': pending_requirements,
        'unplaced_students': unplaced_students,
        'status_segments': status_segments,
        'recent_placements': recent_placements,
        'pending_requirements_list': pending_requirements_list,
        'active_pct': round((active_placements / total_students * 100), 1) if total_students else 0,
        'completed_pct': round((completed_placements / total_students * 100), 1) if total_students else 0,
        'month_labels': month_labels,
        'month_data': month_data,
        'company_names': company_names,
        'company_data': company_data,
        'total_rendered_hours': total_rendered_hours,
        'total_required_hours': total_required_hours,
        'unread_notifications': unread_notifications,
        'recent_notifications': recent_notifications,
    }

    return render(request, 'home.html', context)


@login_required(login_url='login')
def student_dashboard(request):
    email = getattr(request.user, 'email', '') or ''
    if authz.user_role(request.user) == 'supervisor':
        return redirect('supervisor_dashboard')
    student = Student.objects.filter(email__iexact=email).first()
    if not student:
        raise PermissionDenied('No student profile is linked to this account.')

    placements = list(
        student.placements
        .select_related('company', 'supervisor')
        .order_by('-start_date')
    )

    required_hours = sum(
        placement.required_hours
        for placement in placements
        if placement.status != Placement.Status.CANCELLED
    )
    completed_hours = sum(
        placement.completed_hours
        for placement in placements
        if placement.status != Placement.Status.CANCELLED
    )

    pending_requirements = list(
        PlacementRequirement.objects.filter(
            placement__student=student,
            status=PlacementRequirement.Status.PENDING,
        )
        .select_related('placement__student')
        .order_by('date_submitted', 'placement__student__last_name', 'placement__student__first_name')
    )

    evaluations = list(
        PlacementEvaluation.objects.filter(placement__student=student)
        .select_related('placement__company', 'evaluator')
        .order_by('-evaluation_date')
    )

    attendance_records = list(
        Attendance.objects.filter(placement__student=student)
        .select_related('placement__company')
        .order_by('-attendance_date', '-placement__start_date')
    )

    # Filter by date range (GET params from_date / to_date)
    from_date = request.GET.get('from_date', '').strip()
    to_date = request.GET.get('to_date', '').strip()
    filtered = list(attendance_records)
    if from_date:
        filtered = [r for r in filtered if str(r.attendance_date) >= from_date]
    if to_date:
        filtered = [r for r in filtered if str(r.attendance_date) <= to_date]
    # Only supervisor-verified hours count toward OJT completion
    accumulated_hours = round(sum(float(r.hours_rendered or 0) for r in filtered if r.verified), 2)
    accumulated_pct = round((accumulated_hours / required_hours * 100), 1) if required_hours else 0
    pending_verification = sum(1 for r in attendance_records if not r.verified)

    context = {
        'student': student,
        'student_name': f'{student.first_name} {student.last_name}'.strip(),
        'student_number': student.student_number,
        'placements': placements,
        'active_placements': [p for p in placements if p.status == Placement.Status.IN_PROGRESS],
        'completed_placements': [p for p in placements if p.status == Placement.Status.COMPLETED],
        'cancelled_placements': [p for p in placements if p.status == Placement.Status.CANCELLED],
        'pending_requirements': pending_requirements,
        'evaluations': evaluations,
        'attendance_records': filtered,
        'required_hours': required_hours,
        'completed_hours': completed_hours,
        'accumulated_hours': accumulated_hours,
        'accumulated_pct': accumulated_pct,
        'pending_verification': pending_verification,
        'from_date': from_date,
        'to_date': to_date,
        'hours_pct': round((completed_hours / required_hours * 100), 1) if required_hours else 0,
    }

    return render(request, 'student_dashboard.html', context)


@login_required(login_url='login')
@require_POST
def student_time_in(request):
    email = getattr(request.user, 'email', '') or ''
    student = Student.objects.filter(email__iexact=email).first()
    if not student:
        return redirect('dashboard')

    placement = student.placements.filter(status=Placement.Status.IN_PROGRESS).order_by('-start_date').first()
    if not placement:
        messages.error(request, 'No active placement found.')
        return redirect('student_dashboard')

    today = timezone.now().date()
    now = timezone.localtime().time().replace(microsecond=0)
    record, created = Attendance.objects.get_or_create(
        placement=placement,
        attendance_date=today,
        defaults={'time_in': now, 'status': Attendance.Status.PRESENT},
    )
    if not created:
        if record.verified:
            messages.error(request, 'This attendance record is already verified and cannot be changed.')
            return redirect('student_dashboard')
        record.time_in = now
        record.status = Attendance.Status.PRESENT
        record.save()
    messages.success(request, f'Time in recorded at {record.time_in.strftime("%H:%M")}.')
    return redirect('student_dashboard')


@login_required(login_url='login')
@require_POST
def student_time_out(request):
    email = getattr(request.user, 'email', '') or ''
    student = Student.objects.filter(email__iexact=email).first()
    if not student:
        return redirect('dashboard')

    placement = student.placements.filter(status=Placement.Status.IN_PROGRESS).order_by('-start_date').first()
    if not placement:
        messages.error(request, 'No active placement found.')
        return redirect('student_dashboard')

    today = timezone.now().date()
    now = timezone.localtime().time().replace(microsecond=0)
    record = Attendance.objects.filter(placement=placement, attendance_date=today).first()
    if not record:
        record = Attendance.objects.create(
            placement=placement,
            attendance_date=today,
            time_in=now,
            time_out=now,
            status=Attendance.Status.PRESENT,
        )
        messages.success(request, f'Time out recorded at {now.strftime("%H:%M")}. Hours auto-calculated.')
        return redirect('student_dashboard')

    if record.verified:
        messages.error(request, 'This attendance record is already verified and cannot be changed.')
        return redirect('student_dashboard')
    record.time_out = now
    record.save()  # hours_rendered auto-calculated in model save()
    messages.success(request, f'Time out recorded at {now.strftime("%H:%M")}. Hours auto-calculated.')
    return redirect('student_dashboard')


@login_required(login_url='login')
def supervisor_dashboard(request):
    email = getattr(request.user, 'email', '') or ''
    if authz.user_role(request.user) == 'student':
        return redirect('student_dashboard')
    supervisor = Supervisor.objects.filter(email__iexact=email).first()
    if not supervisor:
        raise PermissionDenied('No supervisor profile is linked to this account.')

    placements = list(
        supervisor.placements
        .select_related('student', 'company')
        .order_by('-start_date')
    )

    evaluations = list(
        PlacementEvaluation.objects.filter(evaluator=supervisor)
        .select_related('placement__student', 'placement__company')
        .order_by('-evaluation_date')
    )

    placement_ids = [p.pk for p in placements]
    attendance_records = list(
        Attendance.objects.filter(placement_id__in=placement_ids)
        .select_related('placement__student', 'placement__company')
        .order_by('-attendance_date')
    )

    # Daily required hours from OJT schedule (fallback to 8 hours/day)
    weekday_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
    schedule_hours = {}
    for p in placements:
        for s in p.schedules.all():
            start = datetime.combine(date.today(), s.time_in)
            end = datetime.combine(date.today(), s.time_out)
            if end < start:
                end += timedelta(days=1)
            schedule_hours[(p.pk, s.day_of_week)] = round((end - start).total_seconds() / 3600, 2)

    for record in attendance_records:
        weekday = weekday_map.get(record.attendance_date.weekday(), 'Mon')
        record.daily_required_hours = schedule_hours.get((record.placement_id, weekday), 8)

    # Accumulated (every day) attendance hours vs required hours — verified only counts
    consumed_hours = sum(
        float(record.hours_rendered or 0) for record in attendance_records if record.verified
    )
    completed_hours = sum(
        p.completed_hours or 0 for p in placements if p.status != Placement.Status.CANCELLED
    )
    required_hours = sum(
        p.required_hours for p in placements if p.status != Placement.Status.CANCELLED
    )
    rendered_hours = consumed_hours
    hours_pct = round((consumed_hours / required_hours * 100), 1) if required_hours else 0

    # Real-time student counts for this supervisor
    student_ids = {p.student_id for p in placements}
    total_students = len(student_ids)
    active_placements = [p for p in placements if p.status == Placement.Status.IN_PROGRESS]
    completed_placements = [p for p in placements if p.status == Placement.Status.COMPLETED]
    planned_placements = [p for p in placements if p.status == Placement.Status.PLANNED]
    cancelled_placements = [p for p in placements if p.status == Placement.Status.CANCELLED]
    active_students = len({p.student_id for p in active_placements})
    completed_students = len({p.student_id for p in completed_placements})

    # Today's attendance per student (design: Supervisor Portal table)
    today = timezone.now().date()
    today_records = {
        record.placement_id: record
        for record in Attendance.objects.filter(
            placement__student__in={p.student for p in placements},
            attendance_date=today,
        )
    }
    today_rows = []
    for p in placements:
        if p.status == Placement.Status.CANCELLED:
            continue
        rec = today_records.get(p.pk)
        if rec:
            if rec.status == Attendance.Status.ABSENT:
                status = 'absent'
            elif rec.time_out:
                status = 'completed'
            elif rec.time_in:
                status = 'on-duty'
            else:
                status = 'not-started'
        else:
            status = 'not-started'
        if rec and rec.hours_rendered is not None:
            hrs = float(rec.hours_rendered)
            hours_display = f'{int(hrs)}h {round((hrs - int(hrs)) * 60):02d}m'
        else:
            hours_display = '—'
        status_label = {'on-duty': 'On duty', 'completed': 'Completed', 'not-started': 'Not started', 'absent': 'Absent'}.get(status, 'Not started')
        today_rows.append({
            'placement': p,
            'student': p.student,
            'company': p.company,
            'status': status,
            'status_label': status_label,
            'time_in': rec.time_in if rec else None,
            'time_out': rec.time_out if rec else None,
            'hours': rec.hours_rendered if rec else None,
            'hours_display': hours_display,
            'attendance_pk': rec.pk if rec else None,
            'attendance_date': rec.attendance_date if rec else today,
        })
    assigned_students = len(today_rows)
    clocked_in_now = sum(1 for r in today_rows if r['status'] == 'on-duty')
    completed_today = sum(1 for r in today_rows if r['status'] == 'completed')
    not_clocked_in = sum(1 for r in today_rows if r['status'] in ('not-started', 'absent'))
   
    context = {
        'supervisor': supervisor,
        'supervisor_name': f'{supervisor.first_name} {supervisor.last_name}'.strip(),
        'placements': placements,
        'evaluations': evaluations,
        'attendance_records': attendance_records,
        'active_placements': active_placements,
        'completed_placements': completed_placements,
        'planned_placements': planned_placements,
        'cancelled_placements': cancelled_placements,
        'total_students': total_students,
        'active_students': active_students,
        'completed_students': completed_students,
        'total_placements': len(placements),
        'rendered_hours': round(rendered_hours, 2),
        'consumed_hours': round(consumed_hours, 2),
        'completed_hours': completed_hours,
        'required_hours': required_hours,
        'hours_pct': hours_pct,
        'today': today,
        'today_rows': today_rows,
        'assigned_students': assigned_students,
        'clocked_in_now': clocked_in_now,
        'completed_today': completed_today,
        'not_clocked_in': not_clocked_in,
        'first_placement_id': placements[0].pk if placements else None,
    }

    return render(request, 'supervisor_dashboard.html', context)


@require_http_methods(['GET', 'POST'])
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'GET':
        return render(request, 'auth/register.html')

    form_data = {
        'username': request.POST.get('username', ''),
        'first_name': request.POST.get('first_name', ''),
        'last_name': request.POST.get('last_name', ''),
        'email': request.POST.get('email', ''),
        'student_number': request.POST.get('student_number', ''),
    }

    errors = _validate_registration_data(form_data)
    if errors:
        return render(request, 'auth/register.html', {'errors': errors, 'form_data': form_data})

    student_number = form_data['student_number'].strip()
    # The student's password is their student number for a frictionless first login
    user = User.objects.create_user(
        username=form_data['username'].strip(),
        first_name=form_data['first_name'].strip(),
        last_name=form_data['last_name'].strip(),
        email=form_data['email'].strip(),
        password=student_number,
    )

    Student.objects.create(
        student_number=student_number,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
    )

    login(request, user)
    return redirect('dashboard')


@login_required(login_url='login')
@admin_required
@require_http_methods(['GET', 'POST'])
def supervisor_register_view(request):
    # Supervisor accounts are created by an administrator from Accounts & Roles
    if request.method == 'GET':
        return render(request, 'auth/supervisor_register.html')

    form_data = {
        'first_name': request.POST.get('first_name', ''),
        'last_name': request.POST.get('last_name', ''),
        'email': request.POST.get('email', ''),
        'password': request.POST.get('password', ''),
        'confirm_password': request.POST.get('confirm_password', ''),
        'supervisor_type': request.POST.get('supervisor_type', Supervisor.Type.COMPANY),
    }

    errors = _validate_supervisor_registration_data(form_data)
    if errors:
        return render(request, 'auth/supervisor_register.html', {'errors': errors, 'form_data': form_data})

    # An admin is creating this account, so it is active immediately (no pending approval needed)
    user = User.objects.create_user(
        username=form_data['email'].strip(),
        first_name=form_data['first_name'].strip(),
        last_name=form_data['last_name'].strip(),
        email=form_data['email'].strip(),
        password=form_data['password'],
    )

    Supervisor.objects.create(
        supervisor_type=form_data['supervisor_type'],
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
    )

    messages.success(request, f'Supervisor account for {user.email} created and ready to use.')
    return render(request, 'auth/supervisor_created.html', {'created_user': user})


@login_required(login_url='login')
def approvals_view(request):
    if not authz.is_admin(request.user):
        return redirect('dashboard')
    pending = [
        {
            'user': user,
            'supervisor': Supervisor.objects.filter(email__iexact=user.email).first(),
        }
        for user in User.objects.filter(is_active=False).order_by('date_joined')
        if Supervisor.objects.filter(email__iexact=user.email).exists()
    ]
    return render(request, 'approvals.html', {
        'pending': pending,
    })


@login_required(login_url='login')
@require_POST
def approve_supervisor(request, user_id):
    if not authz.is_admin(request.user):
        return redirect('dashboard')
    user = get_object_or_404(User, pk=user_id, is_active=False)
    user.is_active = True
    user.save()
    messages.success(request, f'{user.get_full_name() or user.username} approved as supervisor.')
    return redirect('approvals')


@login_required(login_url='login')
@require_POST
def reject_supervisor(request, user_id):
    if not authz.is_admin(request.user):
        return redirect('dashboard')
    user = get_object_or_404(User, pk=user_id, is_active=False)
    Supervisor.objects.filter(email__iexact=user.email).delete()
    user.delete()
    messages.success(request, 'Supervisor application rejected and removed.')
    return redirect('approvals')
@admin_required
def accounts_view(request):
    """Admin page to view accounts and set their role (student/supervisor/none)."""
    query = request.GET.get('q', '').strip()
    users = User.objects.prefetch_related('groups').order_by('-is_active', 'username')
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    paginator = Paginator(users, 15)
    page = paginator.get_page(request.GET.get('page'))
    rows = []
    for account in page.object_list:
        groups = {group.name for group in account.groups.all()}
        if 'student' in groups:
            role = 'student'
        elif 'supervisor' in groups:
            role = 'supervisor'
        else:
            role = 'admin'
        rows.append({'account': account, 'role': role})
    return render(request, 'accounts.html', {
        'rows': rows,
        'page': page,
        'query': query,
    })


def _unique_student_number():
    from uuid import uuid4
    while True:
        candidate = f'OJT-{uuid4().hex[:6].upper()}'
        if not Student.objects.filter(student_number=candidate).exists():
            return candidate


@admin_required
@require_POST
def account_action(request, user_id):
    """Apply a role/status action to an account (admin only)."""
    target = get_object_or_404(User, pk=user_id)
    action = request.POST.get('action', '')

    # Guard rails: never let an admin lock out themselves or break superusers
    if target.pk == request.user.pk:
        messages.error(request, 'You cannot change your own account here.')
        return redirect('accounts')
    if target.is_superuser:
        messages.error(request, 'Superuser accounts cannot be modified here.')
        return redirect('accounts')

    student_group, _ = Group.objects.get_or_create(name='student')
    supervisor_group, _ = Group.objects.get_or_create(name='supervisor')

    if action == 'set_student':
        target.groups.remove(supervisor_group)
        target.groups.add(student_group)
        if (target.email or '').strip() and not Student.objects.filter(email__iexact=target.email).exists():
            Student.objects.create(
                student_number=_unique_student_number(),
                first_name=target.first_name or target.username,
                last_name=target.last_name or '—',
                email=target.email,
            )
        messages.success(request, f'{target.username} is now a student account.')
    elif action == 'set_supervisor':
        target.groups.remove(student_group)
        target.groups.add(supervisor_group)
        if (target.email or '').strip() and not Supervisor.objects.filter(email__iexact=target.email).exists():
            Supervisor.objects.create(
                supervisor_type=Supervisor.Type.COMPANY,
                first_name=target.first_name or target.username,
                last_name=target.last_name or '—',
                email=target.email,
            )
        messages.success(request, f'{target.username} is now a supervisor account.')
    elif action == 'clear_role':
        target.groups.remove(student_group, supervisor_group)
        messages.success(request, f'Role cleared for {target.username}.')
    elif action == 'toggle_active':
        target.is_active = not target.is_active
        target.save(update_fields=['is_active'])
        messages.success(request, f'{target.username} {"activated" if target.is_active else "deactivated"}.')
    elif action == 'toggle_staff':
        target.is_staff = not target.is_staff
        target.save(update_fields=['is_staff'])
        messages.success(request, f'{target.username} staff access {"granted" if target.is_staff else "revoked"}.')
    else:
        messages.error(request, 'Unknown action.')
    return redirect('accounts')
