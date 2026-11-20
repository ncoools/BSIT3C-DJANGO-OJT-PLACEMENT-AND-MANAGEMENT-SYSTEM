from django.db import migrations


def require_change_for_existing_students(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    PasswordState = apps.get_model('core', 'PasswordState')

    for user in User.objects.filter(groups__name='student').distinct():
        PasswordState.objects.update_or_create(
            user=user,
            defaults={'must_change_password': True},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(require_change_for_existing_students, noop),
    ]
