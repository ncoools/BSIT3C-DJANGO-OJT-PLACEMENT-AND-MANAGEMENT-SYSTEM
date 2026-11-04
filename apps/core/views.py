from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Count
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.companies.models import Company
from apps.departments.models import Department
from apps.placements.models import Placement, PlacementRequirement
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
    total_students = Student.objects.count()
    partner_companies = Company.objects.count()
    total_placements = Placement.objects.count()
    active_placements = Placement.objects.filter(status=Placement.Status.IN_PROGRESS).count()
    completed_placements = Placement.objects.filter(status=Placement.Status.COMPLETED).count()
    pending_requirements = PlacementRequirement.objects.filter(status=PlacementRequirement.Status.PENDING).count()
    unplaced_students = Student.objects.filter(placements__isnull=True).distinct().count()

    departments = list(
        Department.objects
        .annotate(student_count=Count('students'))
        .order_by('-student_count', 'department_name')
    )
    max_students = max((dept.student_count for dept in departments), default=0)
    department_stats = [
        {
            'department_name': dept.department_name,
            'student_count': dept.student_count,
            'student_width': round((dept.student_count / max_students * 100), 0) if max_students else 0,
        }
        for dept in departments
    ]

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
        'department_stats': department_stats,
        'status_segments': status_segments,
        'recent_placements': recent_placements,
        'pending_requirements_list': pending_requirements_list,
        'active_pct': round((active_placements / total_students * 100), 1) if total_students else 0,
        'completed_pct': round((completed_placements / total_students * 100), 1) if total_students else 0,
    }

    return render(request, 'home.html', context)


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
    login(request, user)
    return redirect('dashboard')
