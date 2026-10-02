from datetime import date

from django.db import migrations


HOLIDAYS = [
    (date(2026, 1, 26), 'Republic Day'),
    (date(2026, 8, 15), 'Independence Day'),
    (date(2026, 10, 2), 'Gandhi Jayanti'),
]


def add_holidays(apps, schema_editor):
    CompanyHoliday = apps.get_model('core', 'CompanyHoliday')
    for holiday_date, name in HOLIDAYS:
        CompanyHoliday.objects.get_or_create(date=holiday_date, defaults={'name': name})


def remove_holidays(apps, schema_editor):
    CompanyHoliday = apps.get_model('core', 'CompanyHoliday')
    for holiday_date, name in HOLIDAYS:
        CompanyHoliday.objects.filter(date=holiday_date, name=name).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0008_companyholiday_leaveapplication_approval_notes_and_more'),
    ]

    operations = [
        migrations.RunPython(add_holidays, remove_holidays),
    ]