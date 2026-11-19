"""
Keep the 'student' and 'supervisor' auth groups in sync with
Student / Supervisor profile records (matched by email).
"""
from django.apps import apps
from django.contrib.auth.models import Group
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


def _sync_user_groups(user):
    if not user or not user.is_authenticated:
        return
    email = (user.email or '').strip()
    if not email:
        return
    student_group = Group.objects.filter(name='student').first()
    supervisor_group = Group.objects.filter(name='supervisor').first()
    if student_group:
        student_group.user_set.remove(user)
    if supervisor_group:
        supervisor_group.user_set.remove(user)

    Student = apps.get_model('student_records', 'Student')
    Supervisor = apps.get_model('supervisors', 'Supervisor')

    if Student.objects.filter(email__iexact=email).exists():
        if student_group:
            student_group.user_set.add(user)
    elif Supervisor.objects.filter(email__iexact=email).exists():
        if supervisor_group:
            supervisor_group.user_set.add(user)


@receiver(post_save, sender=apps.get_model('student_records', 'Student'))
def student_saved(sender, instance, **kwargs):
    email = (instance.email or '').strip()
    if not email:
        return
    from django.contrib.auth import get_user_model
    for user in get_user_model().objects.filter(email__iexact=email):
        _sync_user_groups(user)


@receiver(post_delete, sender=apps.get_model('student_records', 'Student'))
def student_deleted(sender, instance, **kwargs):
    email = (instance.email or '').strip()
    if not email:
        return
    from django.contrib.auth import get_user_model
    for user in get_user_model().objects.filter(email__iexact=email):
        _sync_user_groups(user)


@receiver(post_save, sender=apps.get_model('supervisors', 'Supervisor'))
def supervisor_saved(sender, instance, **kwargs):
    email = (instance.email or '').strip()
    if not email:
        return
    from django.contrib.auth import get_user_model
    for user in get_user_model().objects.filter(email__iexact=email):
        _sync_user_groups(user)


@receiver(post_delete, sender=apps.get_model('supervisors', 'Supervisor'))
def supervisor_deleted(sender, instance, **kwargs):
    email = (instance.email or '').strip()
    if not email:
        return
    from django.contrib.auth import get_user_model
    for user in get_user_model().objects.filter(email__iexact=email):
        _sync_user_groups(user)
