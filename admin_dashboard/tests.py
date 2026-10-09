import datetime
import tempfile
from decimal import Decimal
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.test import override_settings

from core.models import (
    Attendance,
    AttendanceCorrectionRequest,
    CompanyHoliday,
    Department,
    Designation,
    LeaveApplication,
    Salary,
    SalaryComponent,
    SalaryRevision,
    SalaryStructure,
    User,
)


class AdminDashboardTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='dashboard-admin',
            password='test-password',
            role='admin',
        )
        self.employee = User.objects.create_user(
            username='dashboard-employee',
            password='test-password',
            role='employee',
            is_active=True,
        )
        self.inactive_employee = User.objects.create_user(
            username='inactive-employee',
            password='test-password',
            role='employee',
            is_active=False,
        )

    def test_admin_dashboard_uses_existing_hr_records(self):
        today = timezone.localdate()
        Attendance.objects.create(
            employee=self.employee,
            date=today,
            status='present',
        )
        LeaveApplication.objects.create(
            employee=self.employee,
            start_date=today + datetime.timedelta(days=1),
            end_date=today + datetime.timedelta(days=2),
            reason='Personal leave',
            leave_type='Casual',
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['employee_count'], 1)
        self.assertEqual(response.context['present_count'], 1)
        self.assertEqual(response.context['half_day_count'], 0)
        self.assertEqual(response.context['absent_count'], 0)
        self.assertEqual(response.context['pending_leave_count'], 1)
        self.assertEqual(response.context['pending_applications'].count(), 1)
        self.assertContains(response, 'dashboard-employee')

    def test_dashboard_analytics_and_widgets_use_database_records(self):
        today = timezone.localdate()
        self.employee.department = 'Engineering'
        self.employee.joining_date = today
        birthday = today + datetime.timedelta(days=2)
        birthday_year = 2000 if (birthday.month, birthday.day) == (2, 29) else 1990
        self.employee.date_of_birth = datetime.date(
            birthday_year, birthday.month, birthday.day
        )
        self.employee.save(update_fields=['department', 'joining_date', 'date_of_birth'])
        colleague = User.objects.create_user(
            username='operations-employee',
            password='test-password',
            role='employee',
            department='Operations',
            joining_date=today.replace(year=today.year - 1),
        )
        employee_on_leave = User.objects.create_user(
            username='finance-employee',
            password='test-password',
            role='employee',
            department='Finance',
        )
        Attendance.objects.create(
            employee=self.employee,
            date=today,
            status='present',
            check_in=datetime.time(9, 16),
        )
        Attendance.objects.create(
            employee=colleague,
            date=today,
            status='absent',
        )
        Attendance.objects.create(
            employee=employee_on_leave,
            date=today,
            status='leave',
        )
        LeaveApplication.objects.create(
            employee=self.employee,
            start_date=today + datetime.timedelta(days=3),
            end_date=today + datetime.timedelta(days=4),
            reason='Personal leave',
            leave_type='Casual',
        )
        LeaveApplication.objects.create(
            employee=employee_on_leave,
            start_date=today,
            end_date=today,
            reason='Approved day off',
            leave_type='Paid',
            status='approved',
        )
        AttendanceCorrectionRequest.objects.create(
            employee=colleague,
            date=today,
            reason='Missed check-out',
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_employee_count'], 4)
        self.assertEqual(response.context['active_employee_count'], 3)
        self.assertEqual(response.context['present_count'], 1)
        self.assertEqual(response.context['absent_count'], 1)
        self.assertEqual(response.context['employees_on_leave'], 1)
        self.assertEqual(response.context['late_arrival_count'], 1)
        self.assertEqual(response.context['pending_leave_count'], 1)
        self.assertEqual(response.context['new_joiner_count'], 1)
        self.assertEqual(response.context['department_count'], 3)
        self.assertEqual(response.context['attendance_percentage'], 50.0)
        self.assertEqual(
            [item['percentage'] for item in response.context['employee_attendance_summary']],
            [0.0, 100.0],
        )
        self.assertEqual(response.context['attendance_day_chart']['values'], [1, 1, 1, 0])
        current_month_index = response.context['attendance_trend_chart']['labels'].index(
            today.strftime('%b %Y')
        )
        self.assertEqual(
            response.context['attendance_trend_chart']['present'][current_month_index],
            1,
        )
        self.assertEqual(
            response.context['attendance_trend_chart']['absent'][current_month_index],
            1,
        )
        self.assertEqual(
            response.context['attendance_trend_chart']['leave'][current_month_index],
            1,
        )
        self.assertEqual(len(response.context['hiring_trend_chart']['labels']), 12)
        self.assertEqual(
            response.context['hiring_trend_chart']['values'][current_month_index],
            1,
        )
        self.assertEqual(len(response.context['department_distribution']), 3)
        self.assertEqual(len(response.context['upcoming_birthdays']), 1)
        self.assertEqual(len(response.context['upcoming_anniversaries']), 1)
        self.assertTrue(response.context['recent_activities'])
        self.assertEqual(len(response.context['recent_notifications']), 2)
        self.assertContains(response, 'Recent Notifications')
        self.assertContains(response, 'Attendance correction requested')

    def test_dashboard_shows_empty_states_when_records_are_missing(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['attendance_percentage'])
        self.assertContains(response, 'No attendance records for this period.')
        self.assertContains(response, 'No pending leave approvals.')
        self.assertContains(response, 'No pending notifications.')
        self.assertContains(response, 'Employee account created')

    def test_admin_navigation_is_grouped_and_mobile_toggle_is_accessible(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'People &amp; Organization')
        self.assertContains(response, 'Operations')
        self.assertContains(response, 'aria-label="Open navigation"')
        self.assertContains(response, 'aria-controls="primary-sidebar"')
        self.assertContains(response, 'data-sidebar-toggle')
        self.assertContains(response, 'data-sidebar-close')

    def test_root_opens_login_page_for_authenticated_admin(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('root_redirect'), follow=True)

        self.assertRedirects(response, reverse('login'))
        self.assertContains(response, 'HRMS Employee Portal')

    def test_root_redirects_anonymous_user_to_login_page(self):
        response = self.client.get(reverse('root_redirect'), follow=True)

        self.assertRedirects(response, reverse('login'))
        self.assertContains(response, 'HRMS Employee Portal')

    def test_login_alias_opens_employee_login_page(self):
        response = self.client.get(reverse('login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'HRMS Employee Portal')

    def test_admin_login_redirects_to_admin_dashboard(self):
        response = self.client.post(
            reverse('admin_login'),
            {'username': self.admin.username, 'password': 'test-password'},
            follow=True,
        )

        self.assertRedirects(response, reverse('admin_dashboard'))

    def test_employee_login_redirects_to_employee_dashboard(self):
        response = self.client.post(
            reverse('admin_login'),
            {'username': self.employee.username, 'password': 'test-password'},
            follow=True,
        )

        self.assertRedirects(response, reverse('employee_dashboard'))

    def test_authenticated_user_visiting_login_sees_login_form(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('admin_login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'HRMS Admin Portal')

    def test_dashboard_is_restricted_to_admin_role(self):
        self.client.force_login(self.employee)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Admin access required', status_code=403)
        self.assertContains(response, 'Log out and switch account', status_code=403)

    def test_admin_can_add_company_holiday_range_from_leave_calendar(self):
        holiday_start = datetime.date(2026, 12, 25)
        holiday_end = datetime.date(2026, 12, 27)
        self.client.force_login(self.admin)

        response = self.client.post(reverse('admin_leave_calendar'), {
            'start_date': holiday_start.isoformat(),
            'end_date': holiday_end.isoformat(),
            'name': 'Christmas Day',
        })

        holidays = CompanyHoliday.objects.filter(
            date__range=(holiday_start, holiday_end),
        ).order_by('date')
        self.assertEqual(holidays.count(), 3)
        self.assertEqual(list(holidays.values_list('name', flat=True)), ['Christmas Day'] * 3)
        self.assertRedirects(
            response,
            f"{reverse('admin_leave_calendar')}?month=12&year=2026",
        )
        calendar_response = self.client.get(reverse('admin_leave_calendar'), {
            'month': 12,
            'year': 2026,
        })
        self.assertContains(calendar_response, 'Christmas Day')
        self.assertNotContains(calendar_response, 'Approved leave</span>')
        self.assertNotContains(calendar_response, 'Company holiday</span>')

    def test_admin_can_undo_company_holiday_from_calendar(self):
        holiday = CompanyHoliday.objects.create(
            date=datetime.date(2026, 12, 25),
            name='Christmas Day',
        )
        self.client.force_login(self.admin)

        response = self.client.post(reverse('admin_leave_calendar'), {
            'holiday_id': holiday.pk,
        })

        self.assertRedirects(
            response,
            f"{reverse('admin_leave_calendar')}?month=12&year=2026",
        )
        self.assertFalse(CompanyHoliday.objects.filter(pk=holiday.pk).exists())

    def test_employee_cannot_add_company_holiday(self):
        self.client.force_login(self.employee)

        response = self.client.post(reverse('admin_leave_calendar'), {
            'start_date': '2026-12-25',
            'end_date': '2026-12-25',
            'name': 'Christmas Day',
        })

        self.assertRedirects(response, reverse('employee_dashboard'))
        self.assertFalse(CompanyHoliday.objects.filter(name='Christmas Day').exists())


class DepartmentAndPayrollManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='organization-payroll-admin',
            password='test-password',
            role='admin',
        )
        self.employee = User.objects.create_user(
            username='organization-payroll-employee',
            password='test-password',
            first_name='Jordan',
            last_name='Employee',
            role='employee',
            is_active=True,
        )
        self.client.force_login(self.admin)

    def test_department_head_hierarchy_and_employee_designation_assignment(self):
        response = self.client.post(reverse('organization_management'), {
            'action': 'department',
            'name': 'Engineering',
            'description': 'Product engineering',
            'head': str(self.employee.pk),
            'parent_department': '',
            'is_active': 'on',
        })

        self.assertRedirects(response, reverse('organization_management'))
        department = Department.objects.get(name='Engineering')
        self.employee.refresh_from_db()
        self.assertEqual(department.head, self.employee)
        self.assertEqual(self.employee.department_record, department)
        self.assertEqual(self.employee.department, 'Engineering')

        self.client.post(reverse('organization_management'), {
            'action': 'designation',
            'department': str(department.pk),
            'name': 'Software Engineer',
            'description': '',
            'is_active': 'on',
        })
        designation = Designation.objects.get(name='Software Engineer')
        self.employee.designation_record = designation
        self.employee.save(update_fields=['designation_record'])
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.designation, 'Software Engineer')

        child_response = self.client.post(reverse('organization_management'), {
            'action': 'department',
            'name': 'Platform',
            'description': '',
            'head': '',
            'parent_department': str(department.pk),
            'is_active': 'on',
        })
        self.assertRedirects(child_response, reverse('organization_management'))
        self.assertEqual(Department.objects.get(name='Platform').parent_department, department)
        page = self.client.get(reverse('organization_management'))
        self.assertContains(page, 'Software Engineer')
        self.assertContains(page, 'Platform')

    def test_department_head_must_be_assigned_to_the_same_department(self):
        other_department = Department.objects.create(name='Operations')
        self.employee.department_record = other_department
        self.employee.department = other_department.name
        self.employee.save(update_fields=['department_record', 'department'])

        response = self.client.post(reverse('organization_management'), {
            'action': 'department',
            'name': 'Engineering',
            'description': '',
            'head': str(self.employee.pk),
            'parent_department': '',
            'is_active': 'on',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['department_form'].errors['head'])
        self.assertFalse(Department.objects.filter(name='Engineering').exists())

    def test_department_hierarchy_rejects_cycles(self):
        parent = Department.objects.create(name='Engineering')
        child = Department.objects.create(
            name='Platform',
            parent_department=parent,
        )

        response = self.client.post(reverse('organization_management'), {
            'action': 'department',
            'department_id': str(parent.pk),
            'name': parent.name,
            'description': '',
            'head': '',
            'parent_department': str(child.pk),
            'is_active': 'on',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.context['department_form'].errors['parent_department']
        )
        parent.refresh_from_db()
        self.assertIsNone(parent.parent_department_id)

    def test_employee_cannot_access_admin_department_or_payroll_views(self):
        self.client.force_login(self.employee)

        for route in ('organization_management', 'payroll_management', 'payroll_report_export'):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertRedirects(response, reverse('employee_dashboard'))

    def test_monthly_payroll_calculates_attendance_deduction_once_and_payslip_access(self):
        month, year = 9, 2026
        start_date = datetime.date(year, month, 1)
        last_date = datetime.date(year, month, 30)
        workdays = [
            start_date + datetime.timedelta(days=offset)
            for offset in range((last_date - start_date).days + 1)
            if (start_date + datetime.timedelta(days=offset)).weekday() < 5
        ]
        Attendance.objects.create(
            employee=self.employee,
            date=workdays[0],
            status='absent',
        )
        Attendance.objects.create(
            employee=self.employee,
            date=workdays[1],
            status='absent',
        )
        LeaveApplication.objects.create(
            employee=self.employee,
            start_date=workdays[1],
            end_date=workdays[1],
            reason='Approved personal leave',
            leave_type='Casual',
            status='approved',
        )
        structure = SalaryStructure.objects.create(
            employee=self.employee,
            basic_salary='1000.00',
            hra='200.00',
            allowances='100.00',
            deductions='50.00',
            attendance_based=True,
            effective_from=start_date,
        )
        SalaryRevision.objects.create(
            structure=structure,
            basic_salary='1000.00',
            hra='200.00',
            allowances='100.00',
            deductions='50.00',
            attendance_based=True,
            effective_from=start_date,
            reason='Initial structure',
            revised_by=self.admin,
        )

        response = self.client.post(reverse('payroll_management'), {
            'action': 'process',
            'month': str(month),
            'year': str(year),
        })

        self.assertRedirects(response, f'{reverse("payroll_management")}?month={month}&year={year}')
        salary = Salary.objects.get(employee=self.employee, month=month, year=year)
        unpaid_deduction = (Decimal('1300.00') / Decimal(len(workdays))).quantize(Decimal('0.01'))
        self.assertEqual(salary.amount, Decimal('1300.00') - Decimal('50.00') - unpaid_deduction)
        self.assertEqual(
            salary.components.get(name='Unpaid / Absence Adjustment').amount,
            unpaid_deduction,
        )
        payroll_page = self.client.get(reverse('payroll_management'), {'month': month, 'year': year})
        self.assertEqual(payroll_page.status_code, 200)
        self.assertEqual(len(payroll_page.context['rows']), 1)
        self.assertEqual(payroll_page.context['rows'][0]['salary'], salary)
        report = self.client.get(reverse('payroll_report_export'), {'month': month, 'year': year})
        self.assertEqual(report.status_code, 200)
        self.assertIn('text/csv', report['Content-Type'])
        self.client.post(reverse('payroll_management'), {
            'action': 'process',
            'month': str(month),
            'year': str(year),
        })
        self.assertEqual(Salary.objects.filter(employee=self.employee, month=month, year=year).count(), 1)

        self.client.post(reverse('payroll_management'), {
            'action': 'mark_paid',
            'salary_id': str(salary.pk),
            'month': str(month),
            'year': str(year),
        })
        salary.refresh_from_db()
        self.assertEqual(salary.status, 'paid')
        payslip = self.client.get(reverse('admin_payslip_download', args=[salary.pk]))
        self.assertEqual(payslip.status_code, 200)
        self.assertEqual(payslip['Content-Type'], 'application/pdf')
        self.assertTrue(b''.join(payslip.streaming_content).startswith(b'%PDF'))
        payslip.close()

    def test_salary_structure_changes_record_revision_history(self):
        today = timezone.localdate()
        response = self.client.post(reverse('salary_structure_create'), {
            'employee': str(self.employee.pk),
            'basic_salary': '5000.00',
            'hra': '1200.00',
            'allowances': '350.00',
            'deductions': '125.00',
            'attendance_based': 'on',
            'effective_from': today.isoformat(),
            'is_active': 'on',
            'reason': 'Initial offer',
        })

        self.assertRedirects(response, reverse('payroll_management'))
        structure = SalaryStructure.objects.get(employee=self.employee)
        self.employee.refresh_from_db()
        self.assertEqual(structure.gross_salary, Decimal('6550.00'))
        self.assertEqual(structure.revisions.count(), 1)
        self.assertEqual(structure.revisions.get().reason, 'Initial offer')
        self.assertEqual(self.employee.salary_amount, Decimal('6550.00'))

    def test_payroll_applies_each_salary_revision_for_its_effective_part_of_month(self):
        month, year = 9, 2026
        month_start = datetime.date(year, month, 1)
        structure = SalaryStructure.objects.create(
            employee=self.employee,
            basic_salary='1000.00',
            hra='200.00',
            allowances='100.00',
            deductions='50.00',
            effective_from=month_start,
        )
        SalaryRevision.objects.create(
            structure=structure,
            basic_salary='1000.00',
            hra='200.00',
            allowances='100.00',
            deductions='50.00',
            effective_from=month_start,
            revised_by=self.admin,
        )
        SalaryRevision.objects.create(
            structure=structure,
            basic_salary='2000.00',
            hra='400.00',
            allowances='200.00',
            deductions='100.00',
            effective_from=datetime.date(year, month, 16),
            revised_by=self.admin,
        )

        response = self.client.post(reverse('payroll_management'), {
            'action': 'process',
            'month': str(month),
            'year': str(year),
        })

        self.assertRedirects(
            response,
            f'{reverse("payroll_management")}?month={month}&year={year}',
        )
        salary = Salary.objects.get(employee=self.employee, month=month, year=year)
        self.assertEqual(salary.amount, Decimal('1875.00'))
        self.assertEqual(
            salary.components.get(name='Basic Salary').amount,
            Decimal('1500.00'),
        )
        self.assertEqual(
            salary.components.get(name='HRA').amount,
            Decimal('300.00'),
        )
        self.assertEqual(
            salary.components.get(name='Allowances').amount,
            Decimal('150.00'),
        )
        self.assertEqual(
            salary.components.get(name='Other Deductions').amount,
            Decimal('75.00'),
        )

    def test_salary_structure_employee_cannot_be_changed_during_revision(self):
        structure = SalaryStructure.objects.create(
            employee=self.employee,
            basic_salary='5000.00',
            effective_from=timezone.localdate(),
        )
        other_employee = User.objects.create_user(
            username='other-payroll-employee',
            role='employee',
        )

        response = self.client.post(
            reverse('salary_structure_edit', args=[structure.pk]),
            {
                'employee': str(other_employee.pk),
                'basic_salary': '5500.00',
                'hra': '0.00',
                'allowances': '0.00',
                'deductions': '0.00',
                'attendance_based': 'on',
                'effective_from': timezone.localdate().isoformat(),
                'is_active': 'on',
                'reason': 'Annual review',
            },
        )

        self.assertRedirects(response, reverse('payroll_management'))
        structure.refresh_from_db()
        self.assertEqual(structure.employee, self.employee)
        self.assertEqual(structure.basic_salary, Decimal('5500.00'))

    def test_payroll_and_salary_structure_lists_are_paginated(self):
        month, year = 9, 2026
        for index in range(51):
            employee = User.objects.create_user(
                username=f'paginated-payroll-{index:02d}',
                role='employee',
            )
            SalaryStructure.objects.create(
                employee=employee,
                basic_salary='1000.00',
                effective_from=datetime.date(year, month, 1),
            )
            Salary.objects.create(
                employee=employee,
                month=month,
                year=year,
                amount='1000.00',
            )
            if index == 0:
                Salary.objects.create(
                    employee=employee,
                    month=12,
                    year=timezone.localdate().year - 5,
                    amount='1000.00',
                )

        first_page = self.client.get(
            reverse('payroll_management'),
            {'month': month, 'year': year},
        )
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(len(first_page.context['rows']), 50)
        self.assertEqual(first_page.context['payroll_page'].paginator.count, 51)
        self.assertEqual(len(first_page.context['structures']), 50)
        self.assertEqual(first_page.context['structure_page'].paginator.count, 51)
        self.assertIn(timezone.localdate().year - 5, first_page.context['years'])
        self.assertNotIn(timezone.localdate().year + 1, first_page.context['years'])
        self.assertContains(first_page, 'Page 1 of 2')

        second_page = self.client.get(
            reverse('payroll_management'),
            {'month': month, 'year': year, 'payroll_page': 2, 'structure_page': 2},
        )
        self.assertEqual(len(second_page.context['rows']), 1)
        self.assertEqual(len(second_page.context['structures']), 1)


class EmployeeManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='employee-management-admin',
            password='test-password',
            role='admin',
        )
        cls.employee = User.objects.create_user(
            username='managed-employee',
            password='old-password',
            first_name='Morgan',
            last_name='Employee',
            email='morgan@example.com',
            role='employee',
            department='Engineering',
            designation='Developer',
            joining_date=timezone.localdate(),
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_employee_create_assigns_unique_id_and_password(self):
        response = self.client.post(
            reverse('employee_create'),
            {
                'first_name': 'Casey',
                'last_name': 'Newhire',
                'username': 'casey-newhire',
                'email': 'casey@example.com',
                'department': 'Product',
                'designation': 'Analyst',
                'joining_date': timezone.localdate().isoformat(),
                'employment_status': 'active',
                'salary_amount': '0.00',
                'password': 'temporary-password',
            },
            follow=True,
        )

        employee = User.objects.get(username='casey-newhire')
        self.assertRedirects(response, reverse('employee_detail', args=[employee.pk]))
        self.assertEqual(employee.role, 'employee')
        self.assertRegex(employee.employee_id, r'^EMP\d{6}$')
        self.assertEqual(employee.department_record.name, 'Product')
        self.assertEqual(employee.designation_record.name, 'Analyst')
        self.assertTrue(employee.check_password('temporary-password'))
        self.assertTrue(employee.is_active)
        self.assertTrue(employee.management_activities.filter(activity_type='created').exists())

    def test_employee_create_form_renders(self):
        response = self.client.get(reverse('employee_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create Employee')
        self.assertContains(response, 'Profile photo')

    def test_employee_create_rejects_weak_passwords(self):
        response = self.client.post(
            reverse('employee_create'),
            {
                'first_name': 'Casey',
                'last_name': 'Newhire',
                'username': 'weak-password-user',
                'employment_status': 'active',
                'salary_amount': '0.00',
                'password': 'password',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='weak-password-user').exists())
        self.assertTrue(response.context['form'].errors['password'])

    def test_employee_edit_updates_profile_and_lifecycle_status(self):
        response = self.client.post(
            reverse('employee_edit', args=[self.employee.pk]),
            {
                'first_name': 'Morgan',
                'last_name': 'Updated',
                'username': self.employee.username,
                'email': self.employee.email,
                'department': 'Operations',
                'designation': 'Lead',
                'employment_status': 'on_leave',
                'salary_amount': '0.00',
                'password': '',
            },
            follow=True,
        )

        self.employee.refresh_from_db()
        self.assertRedirects(response, reverse('employee_detail', args=[self.employee.pk]))
        self.assertEqual(self.employee.last_name, 'Updated')
        self.assertEqual(self.employee.department, 'Operations')
        self.assertEqual(self.employee.department_record.name, 'Operations')
        self.assertEqual(self.employee.designation_record.name, 'Lead')
        self.assertEqual(self.employee.employment_status, 'on_leave')
        self.assertTrue(self.employee.is_active)
        self.assertTrue(self.employee.check_password('old-password'))
        self.assertTrue(
            self.employee.management_activities.filter(
                activity_type='status_changed'
            ).exists()
        )

    def test_employee_deactivation_preserves_profile_but_revokes_login(self):
        response = self.client.post(reverse('employee_deactivate', args=[self.employee.pk]))

        self.employee.refresh_from_db()
        self.assertRedirects(response, reverse('employee_detail', args=[self.employee.pk]))
        self.assertFalse(self.employee.is_active)
        self.assertEqual(self.employee.employment_status, 'active')
        self.assertTrue(
            self.employee.management_activities.filter(
                activity_type='deactivated'
            ).exists()
        )

    def test_employee_account_can_be_reactivated(self):
        self.employee.is_active = False
        self.employee.save(update_fields=['is_active'])

        response = self.client.post(reverse('employee_activate', args=[self.employee.pk]))

        self.employee.refresh_from_db()
        self.assertRedirects(response, reverse('employee_detail', args=[self.employee.pk]))
        self.assertTrue(self.employee.is_active)
        self.assertTrue(
            self.employee.management_activities.filter(
                activity_type='reactivated'
            ).exists()
        )

    def test_employee_directory_search_filter_sort_and_paginate(self):
        User.objects.bulk_create([
            User(
                username=f'directory-{index:02d}',
                first_name=f'Person{index:02d}',
                role='employee',
                employee_id=f'TEST{index:04d}',
                employment_status='on_leave' if index % 2 else 'active',
                department='Engineering' if index % 2 else 'Finance',
            )
            for index in range(16)
        ])

        response = self.client.get(
            reverse('employee_list'),
            {
                'search': 'morgan@example.com',
                'department': 'Engineering',
                'status': 'active',
                'sort': 'employee_id',
                'direction': 'desc',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['paginator'].count, 1)
        self.assertEqual(response.context['employees'][0].pk, self.employee.pk)

        response = self.client.get(
            reverse('employee_list'),
            {'sort': 'employee_id', 'direction': 'desc', 'page': 2},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['paginator'].count, 17)
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(response.context['page_obj'].number, 2)
        self.assertContains(response, 'Page 2 of 2')

    def test_employee_profile_shows_timeline_documents_and_employee_id(self):
        response = self.client.get(reverse('employee_detail', args=[self.employee.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['employee'].employee_id, self.employee.employee_id)
        self.assertContains(response, self.employee.employee_id)
        self.assertContains(response, 'Profile Activity')
        self.assertEqual(response.context['activity_timeline'][0]['title'], 'Employee account created')

    def test_employee_document_upload_download_and_delete(self):
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=Path(media_root)):
                response = self.client.post(
                    reverse('employee_document_upload', args=[self.employee.pk]),
                    {
                        'title': 'Signed offer',
                        'category': 'offer_letter',
                        'file': SimpleUploadedFile(
                            'offer.pdf',
                            b'%PDF-1.4 employee offer',
                            content_type='application/pdf',
                        ),
                    },
                )
                document = self.employee.documents.get(title='Signed offer')
                self.assertTrue(
                    self.employee.management_activities.filter(
                        activity_type='document_uploaded'
                    ).exists()
                )
                self.assertRedirects(
                    response,
                    reverse('employee_detail', args=[self.employee.pk]),
                )

                download_response = self.client.get(
                    reverse(
                        'employee_document_download',
                        args=[self.employee.pk, document.pk],
                    )
                )
                self.assertEqual(download_response.status_code, 200)
                self.assertIn('attachment', download_response['Content-Disposition'])
                download_response.close()

                delete_response = self.client.post(
                    reverse(
                        'employee_document_delete',
                        args=[self.employee.pk, document.pk],
                    )
                )
                self.assertRedirects(
                    delete_response,
                    reverse('employee_detail', args=[self.employee.pk]),
                )
                self.assertFalse(self.employee.documents.filter(pk=document.pk).exists())
                self.assertTrue(
                    self.employee.management_activities.filter(
                        activity_type='document_deleted'
                    ).exists()
                )

    def test_employee_documents_cannot_be_accessed_through_another_profile(self):
        other_employee = User.objects.create_user(
            username='another-employee',
            password='test-password',
            role='employee',
        )
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=Path(media_root)):
                document = self.employee.documents.create(
                    title='Private document',
                    category='other',
                    file=SimpleUploadedFile('private.pdf', b'private'),
                )

                response = self.client.get(
                    reverse(
                        'employee_document_download',
                        args=[other_employee.pk, document.pk],
                    )
                )

        self.assertEqual(response.status_code, 404)
