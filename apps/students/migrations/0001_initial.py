# Squashed initial migration: represents the final state of the Student model.

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Student',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('student_number', models.CharField(max_length=20, unique=True)),
                ('first_name', models.CharField(max_length=50)),
                ('last_name', models.CharField(max_length=50)),
                ('email', models.EmailField(blank=True, max_length=100)),
                ('contact_no', models.CharField(blank=True, max_length=20)),
                ('age', models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(19), MaxValueValidator(30)])),
                ('sex', models.CharField(blank=True, choices=[('M', 'Male'), ('F', 'Female')], max_length=10)),
            ],
            options={
                'ordering': ['last_name', 'first_name'],
            },
        ),
    ]
