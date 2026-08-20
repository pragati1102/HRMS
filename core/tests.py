import datetime
from django.test import TestCase
from core.models import User

class SalaryDueDateTestCase(TestCase):
    def test_standard_due_date(self):
        # Joined on the 15th of the month
        emp = User.objects.create(username='emp1', joining_date=datetime.date(2025, 1, 15))
        
        # Reference date is before the 15th. Due date should be the 15th of the current month.
        due = emp.get_next_salary_due_date(reference_date=datetime.date(2026, 2, 10))
        self.assertEqual(due, datetime.date(2026, 2, 15))

        # Reference date is exactly the 15th. Due date should be today.
        due = emp.get_next_salary_due_date(reference_date=datetime.date(2026, 2, 15))
        self.assertEqual(due, datetime.date(2026, 2, 15))

        # Reference date is after the 15th. Due date should be the 15th of the next month.
        due = emp.get_next_salary_due_date(reference_date=datetime.date(2026, 2, 20))
        self.assertEqual(due, datetime.date(2026, 3, 15))

    def test_month_end_boundary_due_date(self):
        # Joined on the 31st (month-end boundary)
        emp = User.objects.create(username='emp_boundary', joining_date=datetime.date(2025, 1, 31))
        
        # Reference date: Feb 1, 2026. Next due date should be Feb 28, 2026 (non-leap year end of month).
        due = emp.get_next_salary_due_date(reference_date=datetime.date(2026, 2, 1))
        self.assertEqual(due, datetime.date(2026, 2, 28))

        # Reference date: Feb 1, 2024. Next due date should be Feb 29, 2024 (leap year end of month).
        due = emp.get_next_salary_due_date(reference_date=datetime.date(2024, 2, 1))
        self.assertEqual(due, datetime.date(2024, 2, 29))

        # Reference date: Nov 1, 2026. Next due date should be Nov 30, 2026 (30-day month end).
        due = emp.get_next_salary_due_date(reference_date=datetime.date(2026, 11, 1))
        self.assertEqual(due, datetime.date(2026, 11, 30))

        # Reference date: Dec 31, 2025. Next due date should be today Dec 31, 2025.
        due = emp.get_next_salary_due_date(reference_date=datetime.date(2025, 12, 31))
        self.assertEqual(due, datetime.date(2025, 12, 31))

        # Reference date: Dec 31, 2025, and we check candidate month 12 overflow to candidate month 1 (Jan 31).
        due = emp.get_next_salary_due_date(reference_date=datetime.date(2026, 1, 1))
        self.assertEqual(due, datetime.date(2026, 1, 31))
