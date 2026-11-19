"""
Create the 'student' and 'supervisor' auth groups and backfill existing users.

Role detection now uses group membership instead of matching user emails
against Student/Supervisor profile tables.
"""
from django.db import migrations


def create_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='student')
    Group.objects.get_or_create(name='supervisor')


def assign_existing_users(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    Student = apps.get_model('student_records', 'Student')
    Supervisor = apps.get_model('supervisors', 'Supervisor')

    sgroup = Group.objects.get(name='student')
    supgroup = Group.objects.get(name='supervisor')

    for student in Student.objects.all():
        if student.email:
            for user in User.objects.filter(email__iexact=student.email):
                sgroup.user_set.add(user)

    for sup in Supervisor.objects.all():
        if sup.email:
            for user in User.objects.filter(email__iexact=sup.email):
                supgroup.user_set.add(user)


def remove_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=['student', 'supervisor']).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('student_records', '0001_initial'),
        ('supervisors', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_groups, reverse_code=migrations.RunPython.noop),
        migrations.RunPython(assign_existing_users, reverse_code=remove_groups),
    ]
