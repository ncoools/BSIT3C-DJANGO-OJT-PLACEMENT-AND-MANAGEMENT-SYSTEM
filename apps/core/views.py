import random
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

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


def _generate_student_number():
    base = 'OJT'
    while True:
        candidate = f"{base}-{random.randint(100, 9999)}"
        if not Student.objects.filter(student_number=candidate).exists():
            return candidate


def _validate_registration_data(data):
    errors = {}

    username = data.get('username', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

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

    student_number = data.get('student_number', '').strip()

    if student_number and Student.objects.filter(student_number=student_number).exists():
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
    email = getattr(request.user, 'email', '') or ''
    if email and Student.objects.filter(email__iexact=email).exists():
        return redirect('student_dashboard')
    if email and Supervisor.objects.filter(email__iexact=email).exists():
        return redirect('supervisor_dashboard')

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
    }

    return render(request, 'home.html', context)


@login_required(login_url='login')
def student_dashboard(request):
    email = getattr(request.user, 'email', '') or ''
    if Supervisor.objects.filter(email__iexact=email).exists():
        return redirect('supervisor_dashboard')
    student = Student.objects.filter(email__iexact=email).first()
    if not student:
        return redirect('dashboard')

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
    accumulated_hours = round(sum(float(r.hours_rendered or 0) for r in filtered), 2)
    accumulated_pct = round((accumulated_hours / required_hours * 100), 1) if required_hours else 0

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

    record.time_out = now
    record.save()  # hours_rendered auto-calculated in model save()
    messages.success(request, f'Time out recorded at {now.strftime("%H:%M")}. Hours auto-calculated.')
    return redirect('student_dashboard')


@login_required(login_url='login')
def supervisor_dashboard(request):
    email = getattr(request.user, 'email', '') or ''
    if Student.objects.filter(email__iexact=email).exists():
        return redirect('student_dashboard')
    supervisor = Supervisor.objects.filter(email__iexact=email).first()
    if not supervisor:
        return redirect('dashboard')

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

    # Accumulated (every day) attendance hours vs required hours
    consumed_hours = sum(
        float(record.hours_rendered or 0) for record in attendance_records
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
        'password': request.POST.get('password', ''),
        'confirm_password': request.POST.get('confirm_password', ''),
        'student_number': request.POST.get('student_number', ''),
    }

    errors = _validate_registration_data(form_data)
    if errors:
        return render(request, 'auth/register.html', {'errors': errors, 'form_data': form_data})

    user = User.objects.create_user(
        username=form_data['username'].strip(),
        first_name=form_data['first_name'].strip(),
        last_name=form_data['last_name'].strip(),
        email=form_data['email'].strip(),
        password=form_data['password'],
    )

    student_number = form_data.get('student_number', '').strip()
    if not student_number:
        student_number = _generate_student_number()
    Student.objects.create(
        student_number=student_number,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
    )

    login(request, user)
    return redirect('dashboard')


@require_http_methods(['GET', 'POST'])
def supervisor_register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

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

    login(request, user)
    return redirect('supervisor_dashboard')
