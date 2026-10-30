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
    active_student_ids = Placement.objects.exclude(
        status=Placement.Status.CANCELLED,
    ).values('student_id')
    currently_placed = Placement.objects.filter(
        status__in=[Placement.Status.PLANNED, Placement.Status.IN_PROGRESS],
    ).values('student_id').distinct().count()
    completed = Placement.objects.filter(
        status=Placement.Status.COMPLETED,
    ).values('student_id').distinct().count()

    pending_list = list(
        PlacementRequirement.objects.filter(
            status=PlacementRequirement.Status.SUBMITTED,
        )
        .select_related('placement__student', 'placement__company')
        .order_by('date_submitted', 'pk')[:5]
    )
    pending_requirements = PlacementRequirement.objects.filter(
        status=PlacementRequirement.Status.SUBMITTED,
    ).count()

    status_counts = dict(
        Placement.objects.values_list('status').annotate(count=Count('pk'))
    )
    total_placements = sum(status_counts.values())
    status_summary = [
        {
            'value': value,
            'label': label,
            'count': status_counts.get(value, 0),
            'percent': round(status_counts.get(value, 0) * 100 / total_placements)
            if total_placements else 0,
        }
        for value, label in Placement.Status.choices
    ]

    departments = list(
        Department.objects.annotate(student_count=Count('students'))
        .order_by('-student_count', 'department_name')[:5]
    )
    max_department_students = max(
        (department.student_count for department in departments),
        default=0,
    )
    for department in departments:
        department.bar_percent = (
            round(department.student_count * 100 / max_department_students)
            if max_department_students else 0
        )

    today = timezone.localdate()
    ending_soon = Placement.objects.filter(
        status=Placement.Status.IN_PROGRESS,
        end_date__range=(today, today + timedelta(days=7)),
    ).count()
    recent_placements = list(
        Placement.objects.select_related('student', 'company')
        .order_by('-start_date', '-pk')[:5]
    )
    for placement in recent_placements:
        placement.progress_percent = (
            min(100, round(placement.completed_hours * 100 / placement.required_hours))
            if placement.required_hours else 0
        )

    return render(request, 'home.html', {
        'total_students': total_students,
        'currently_placed': currently_placed,
        'unplaced': Student.objects.exclude(pk__in=active_student_ids).count(),
        'total_companies': Company.objects.count(),
        'pending_requirements': pending_requirements,
        'completed': completed,
        'currently_placed_percent': round(currently_placed * 100 / total_students)
        if total_students else 0,
        'completed_percent': round(completed * 100 / total_students)
        if total_students else 0,
        'recent_placements': recent_placements,
        'pending_list': pending_list,
        'status_summary': status_summary,
        'total_placements': total_placements,
        'department_stats': departments,
        'ending_soon': ending_soon,
    })


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
