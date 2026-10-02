import datetime
import io
import shutil
import tempfile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from openpyxl import load_workbook
from django.utils import timezone
from core.models import Attendance, AttendanceCorrectionRequest, CompanyHoliday, EmployeeDocument, LeaveApplication, Project, ProjectAssignment, ProjectMilestone, ProjectResource, ProjectTask, ProjectTechnology, User, WorkLog

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


class EmployeeProfileTestCase(TestCase):
    def test_profile_shows_employee_details_and_gender_avatar(self):
        employee = User.objects.create_user(
            username='jane',
            email='jane@example.com',
            first_name='Jane',
            last_name='Doe',
            role='employee',
            gender='female',
            address='12 Main Street',
        )
        self.client.force_login(employee)

        response = self.client.get('/api/profile/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(employee.id))
        self.assertContains(response, 'jane@example.com')
        self.assertContains(response, '12 Main Street')
        self.assertContains(response, '👩‍💼')
        self.assertNotContains(response, 'Contact Information')
        self.assertContains(response, 'name="gender"')
        self.assertContains(response, 'name="phone_number"')
        self.assertContains(response, 'name="address"')
        self.assertContains(response, 'Edit Profile')
        self.assertContains(response, 'Personal Information')
        self.assertContains(response, 'Employment / Job Details')
        self.assertContains(response, 'Bank &amp; Payroll Details')
        self.assertContains(response, 'Documents')
        self.assertContains(response, 'Change Password')

    def test_payroll_identifiers_are_masked(self):
        employee = User.objects.create_user(
            username='payroll-user',
            role='employee',
            bank_account_number='1234567890',
            bank_identifier='ABCD0123456',
            tax_id='TAX-123456',
        )
        self.client.force_login(employee)

        response = self.client.get(reverse('employee_profile'))

        self.assertContains(response, '•••• 7890')
        self.assertContains(response, '•••• 3456')
        self.assertNotContains(response, '1234567890')
        self.assertNotContains(response, 'ABCD0123456')
        self.assertNotContains(response, 'TAX-123456')

    def test_profile_saves_gender_phone_and_address(self):
        employee = User.objects.create_user(username='jane', role='employee')
        self.client.force_login(employee)

        response = self.client.post('/api/profile/', {
            'gender': 'female',
            'phone_number': '+1 555 123 4567',
            'address': '12 Main Street',
        })

        self.assertRedirects(response, '/api/profile/')
        employee.refresh_from_db()
        self.assertEqual(employee.gender, 'female')
        self.assertEqual(employee.phone_number, '+1 555 123 4567')
        self.assertEqual(employee.address, '12 Main Street')

    def test_profile_photo_upload_is_private_and_returns_image(self):
        employee = User.objects.create_user(username='photo-user', role='employee')
        self.client.force_login(employee)
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)

        image_data = io.BytesIO()
        Image.new('RGB', (2, 2), color='blue').save(image_data, format='PNG')
        photo = SimpleUploadedFile('profile.png', image_data.getvalue(), content_type='image/png')

        with override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(reverse('employee_profile'), {
                'gender': 'other',
                'date_of_birth': '',
                'personal_email': '',
                'emergency_contact': '',
                'phone_number': '',
                'address': '',
                'profile_photo': photo,
            })
            self.assertRedirects(response, reverse('employee_profile'))

            image_response = self.client.get(reverse('employee_profile_photo'))
            self.assertEqual(image_response.status_code, 200)
            self.assertEqual(image_response['Content-Type'], 'image/png')
            self.assertTrue(b''.join(image_response.streaming_content))
            image_response.close()

            attendance_page = self.client.get(reverse('employee_attendance'))
            self.assertContains(attendance_page, reverse('employee_profile_photo'))

            other_employee = User.objects.create_user(username='photo-viewer', role='employee')
            self.client.force_login(other_employee)
            denied_response = self.client.get(reverse('employee_photo_by_id', args=[employee.pk]))
            self.assertEqual(denied_response.status_code, 404)

            administrator = User.objects.create_user(username='photo-admin', role='admin')
            self.client.force_login(administrator)
            admin_response = self.client.get(reverse('employee_photo_by_id', args=[employee.pk]))
            self.assertEqual(admin_response.status_code, 200)
            self.assertEqual(admin_response['Content-Type'], 'image/png')
            admin_response.close()

    def test_documents_can_only_be_downloaded_by_their_employee(self):
        employee = User.objects.create_user(username='document-owner', role='employee')
        other_employee = User.objects.create_user(username='other-employee', role='employee')
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)

        with override_settings(MEDIA_ROOT=media_root):
            document = EmployeeDocument.objects.create(
                employee=employee,
                title='Offer Letter',
                category='offer_letter',
                file=SimpleUploadedFile('offer.pdf', b'offer contents', content_type='application/pdf'),
            )
            self.client.force_login(employee)
            response = self.client.get(reverse('employee_document_download', args=[document.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertIn('attachment', response['Content-Disposition'])
            self.assertEqual(b''.join(response.streaming_content), b'offer contents')
            response.close()

            self.client.force_login(other_employee)
            denied_response = self.client.get(reverse('employee_document_download', args=[document.pk]))
            self.assertEqual(denied_response.status_code, 404)

    def test_employee_can_change_password(self):
        employee = User.objects.create_user(
            username='password-user',
            role='employee',
            password='OldSecurePassword!2026',
        )
        self.client.force_login(employee)

        response = self.client.post(reverse('employee_password_change'), {
            'old_password': 'OldSecurePassword!2026',
            'new_password1': 'N9!rT4#xQ7@bL2vC',
            'new_password2': 'N9!rT4#xQ7@bL2vC',
        })

        self.assertRedirects(response, reverse('employee_profile'))
        employee.refresh_from_db()
        self.assertTrue(employee.check_password('N9!rT4#xQ7@bL2vC'))


class EmployeeAttendanceTestCase(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(username='attendance-user', role='employee')
        self.other_employee = User.objects.create_user(username='other-attendance-user', role='employee')
        self.client.force_login(self.employee)

    def test_attendance_page_shows_clock_filters_metrics_and_export(self):
        response = self.client.get(reverse('employee_attendance'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'digital-clock')
        self.assertContains(response, 'attendance-month')
        self.assertContains(response, 'Working Hours')
        self.assertNotContains(response, 'Average per Day')
        self.assertContains(response, 'Break Duration')
        self.assertContains(response, 'Request Regularization')
        self.assertContains(response, 'Export CSV')

    def test_checkin_records_location_mode_and_request_ip(self):
        response = self.client.post(reverse('employee_check_in'), {'location_mode': 'office'})

        self.assertRedirects(response, reverse('employee_attendance'))
        attendance = Attendance.objects.get(employee=self.employee, date=timezone.localdate())
        self.assertEqual(attendance.location_mode, 'office')
        self.assertEqual(attendance.check_in_ip, '127.0.0.1')

    def test_break_resume_accumulates_duration(self):
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
            status='present',
            check_in=timezone.localtime().time(),
            break_started_at=timezone.now() - datetime.timedelta(minutes=2),
        )

        response = self.client.post(reverse('employee_attendance_break'))

        self.assertRedirects(response, reverse('employee_attendance'))
        attendance.refresh_from_db()
        self.assertIsNone(attendance.break_started_at)
        self.assertGreaterEqual(attendance.break_seconds, 120)

    def test_correction_request_is_saved_for_authenticated_employee(self):
        correction_date = timezone.localdate() - datetime.timedelta(days=1)

        response = self.client.post(reverse('employee_attendance_correction'), {
            'date': correction_date.isoformat(),
            'requested_check_in': '09:00',
            'requested_check_out': '',
            'reason': 'Forgot to check in',
        })

        self.assertRedirects(response, reverse('employee_attendance'))
        request_record = AttendanceCorrectionRequest.objects.get(employee=self.employee)
        self.assertEqual(request_record.date, correction_date)
        self.assertEqual(request_record.requested_check_in, datetime.time(9, 0))
        self.assertEqual(request_record.status, 'pending')

    def test_csv_export_contains_only_current_employees_records(self):
        today = timezone.localdate()
        Attendance.objects.create(
            employee=self.employee,
            date=today,
            status='present',
            check_in=datetime.time(9, 0),
            check_out=datetime.time(17, 0),
            location_mode='remote',
        )
        Attendance.objects.create(
            employee=self.other_employee,
            date=today,
            status='present',
            check_in=datetime.time(9, 0),
            check_out=datetime.time(17, 0),
        )

        response = self.client.get(reverse('employee_attendance_export'), {'month': today.month, 'year': today.year})

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('remote', response.content.decode())
        self.assertEqual(response.content.decode().count(today.isoformat()), 1)

    def test_monthly_metrics_calculate_hours_overtime_and_punctuality(self):
        today = timezone.localdate()
        first_date = today.replace(day=1)
        second_date = first_date + datetime.timedelta(days=1)
        Attendance.objects.create(
            employee=self.employee,
            date=first_date,
            status='present',
            check_in=datetime.time(9, 30),
            check_out=datetime.time(19, 30),
            break_seconds=3600,
        )
        Attendance.objects.create(
            employee=self.employee,
            date=second_date,
            status='present',
            check_in=datetime.time(9, 0),
            check_out=datetime.time(16, 30),
        )

        response = self.client.get(reverse('employee_attendance'), {
            'month': today.month,
            'year': today.year,
        })

        self.assertEqual(response.context['total_work_time'], '16h 30m')
        self.assertEqual(response.context['average_work_time'], '8h 15m')
        self.assertEqual(response.context['overtime_time'], '1h 00m')
        self.assertEqual(response.context['late_arrivals'], 1)
        self.assertEqual(response.context['early_checkouts'], 1)


class EmployeeWorkLogExportTestCase(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(
            username='task-export-user',
            first_name='Taylor',
            last_name='Employee',
            department='Engineering',
            role='employee',
        )
        self.other_employee = User.objects.create_user(username='other-task-user', role='employee')
        self.client.force_login(self.employee)

    def test_task_page_prefills_next_hourly_slot_from_attendance_and_logs(self):
        today = timezone.localdate()
        Attendance.objects.create(
            employee=self.employee,
            date=today,
            status='present',
            check_in=datetime.time(9, 0),
        )
        WorkLog.objects.create(
            employee=self.employee,
            date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            description='Morning work',
        )

        response = self.client.get(reverse('employee_work_logs'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['suggested_start_time'], datetime.time(10, 0))
        self.assertEqual(response.context['suggested_end_time'], datetime.time(11, 0))
        self.assertContains(response, 'value="10:00"')
        self.assertContains(response, 'value="11:00"')

    def test_task_log_must_fit_inside_checked_in_shift(self):
        today = timezone.localdate()
        Attendance.objects.create(
            employee=self.employee,
            date=today,
            status='present',
            check_in=datetime.time(9, 0),
            check_out=datetime.time(17, 0),
        )

        response = self.client.post(reverse('employee_add_worklog'), {
            'date': today.isoformat(),
            'start_time': '08:00',
            'end_time': '09:00',
            'category': 'Development',
            'description': 'Outside shift',
        })

        self.assertRedirects(response, reverse('employee_work_logs'))
        self.assertFalse(WorkLog.objects.filter(employee=self.employee).exists())

    def test_employee_export_has_monthly_sheets_formulas_and_only_own_data(self):
        today = timezone.localdate()
        prior_date = today.replace(day=1) - datetime.timedelta(days=1)
        for date_value, start_time, end_time, description in (
            (today, datetime.time(9, 0), datetime.time(10, 0), 'Current month task'),
            (prior_date, datetime.time(9, 0), datetime.time(11, 0), 'Previous month task'),
        ):
            Attendance.objects.create(
                employee=self.employee,
                date=date_value,
                status='present',
                check_in=datetime.time(9, 0),
                check_out=datetime.time(17, 0),
            )
            WorkLog.objects.create(
                employee=self.employee,
                date=date_value,
                start_time=start_time,
                end_time=end_time,
                category='Development',
                description=description,
            )
        WorkLog.objects.create(
            employee=self.other_employee,
            date=today,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(10, 0),
            description='Private task',
        )

        response = self.client.get(reverse('employee_work_logs_export'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('spreadsheetml.sheet', response['Content-Type'])
        workbook = load_workbook(io.BytesIO(response.content), data_only=False)
        self.assertIn(today.strftime('%b %Y'), workbook.sheetnames)
        self.assertIn(prior_date.strftime('%b %Y'), workbook.sheetnames)
        current_sheet = workbook[today.strftime('%b %Y')]
        self.assertEqual(current_sheet['B1'].value, 'Taylor Employee')
        self.assertEqual(current_sheet['E1'].value, self.employee.pk)
        self.assertEqual(current_sheet['A4'].value, 'Date')
        self.assertEqual(current_sheet['E5'].value, 'Current month task')
        self.assertEqual(current_sheet['F6'].value, '=SUM(F5:F5)')
        self.assertNotIn('Private task', str([cell.value for row in current_sheet.iter_rows() for cell in row]))

    def test_admin_can_export_an_employee_workbook(self):
        administrator = User.objects.create_user(username='task-export-admin', role='admin')
        self.client.force_login(administrator)

        response = self.client.get(reverse('admin_employee_work_logs_export', args=[self.employee.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertIn('spreadsheetml.sheet', response['Content-Type'])

    def test_employee_cannot_export_another_employees_workbook(self):
        response = self.client.get(reverse('admin_employee_work_logs_export', args=[self.employee.pk]))

        self.assertEqual(response.status_code, 403)


class EmployeeLeaveTestCase(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(
            username='leave-user',
            role='employee',
            casual_leave_quota=4,
            sick_leave_quota=3,
            paid_leave_quota=5,
        )
        self.colleague = User.objects.create_user(username='handover-user', role='employee')
        self.client.force_login(self.employee)

    @staticmethod
    def next_weekday(start=None):
        date_value = start or timezone.localdate() + datetime.timedelta(days=1)
        while date_value.weekday() >= 5:
            date_value += datetime.timedelta(days=1)
        return date_value

    def test_leave_page_shows_type_balances_and_application_controls(self):
        response = self.client.get(reverse('employee_leaves'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Casual Leave')
        self.assertContains(response, 'Sick Leave')
        self.assertContains(response, 'Paid Leave')
        self.assertContains(response, '4 remaining')
        self.assertContains(response, 'Half Day (First Half)')
        self.assertContains(response, 'Total: 0 Working Days')
        self.assertContains(response, 'Application History')
        self.assertContains(response, 'Approved')

    def test_working_day_duration_excludes_weekends_and_company_holidays(self):
        next_monday = self.next_weekday()
        while next_monday.weekday() != 0:
            next_monday += datetime.timedelta(days=1)
        tuesday = next_monday + datetime.timedelta(days=1)
        wednesday = next_monday + datetime.timedelta(days=2)
        CompanyHoliday.objects.create(date=tuesday, name='Company Day')

        response = self.client.post(reverse('employee_apply_leave'), {
            'leave_type': 'Casual',
            'half_day_session': 'full',
            'start_date': next_monday.isoformat(),
            'end_date': wednesday.isoformat(),
            'reason': 'Family appointment',
            'handover_contact': str(self.colleague.pk),
        })

        self.assertRedirects(response, reverse('employee_leaves'))
        application = LeaveApplication.objects.get(employee=self.employee)
        self.assertEqual(application.handover_contact, self.colleague)
        page = self.client.get(reverse('employee_leaves'))
        summary = next(item for item in page.context['leave_quota_summary'] if item['leave_type'] == 'Casual')
        self.assertEqual(summary['pending'], 2)
        self.assertEqual(summary['available'], 2)

    def test_half_day_request_counts_as_half_and_must_be_one_date(self):
        day = self.next_weekday()
        response = self.client.post(reverse('employee_apply_leave'), {
            'leave_type': 'Casual',
            'half_day_session': 'first_half',
            'start_date': day.isoformat(),
            'end_date': day.isoformat(),
            'reason': 'Personal appointment',
        })

        self.assertRedirects(response, reverse('employee_leaves'))
        application = LeaveApplication.objects.get(employee=self.employee)
        self.assertEqual(application.half_day_session, 'first_half')

        second_day = self.next_weekday(day + datetime.timedelta(days=1))
        rejected_response = self.client.post(reverse('employee_apply_leave'), {
            'leave_type': 'Casual',
            'half_day_session': 'second_half',
            'start_date': day.isoformat(),
            'end_date': second_day.isoformat(),
            'reason': 'Another appointment',
        })
        self.assertRedirects(rejected_response, reverse('employee_leaves'))
        self.assertEqual(LeaveApplication.objects.filter(employee=self.employee).count(), 1)

    def test_quota_exhaustion_rejects_request(self):
        day = self.next_weekday()
        LeaveApplication.objects.create(
            employee=self.employee,
            leave_type='Casual',
            start_date=day,
            end_date=day,
            reason='Existing approved day',
            status='approved',
        )
        self.employee.casual_leave_quota = 1
        self.employee.save(update_fields=['casual_leave_quota'])
        requested_day = self.next_weekday(day + datetime.timedelta(days=1))

        response = self.client.post(reverse('employee_apply_leave'), {
            'leave_type': 'Casual',
            'half_day_session': 'full',
            'start_date': requested_day.isoformat(),
            'end_date': requested_day.isoformat(),
            'reason': 'Extra day',
        })

        self.assertRedirects(response, reverse('employee_leaves'))
        self.assertEqual(LeaveApplication.objects.filter(employee=self.employee).count(), 1)

    def test_sick_leave_requires_supporting_document(self):
        day = self.next_weekday()
        response = self.client.post(reverse('employee_apply_leave'), {
            'leave_type': 'Sick',
            'half_day_session': 'full',
            'start_date': day.isoformat(),
            'end_date': day.isoformat(),
            'reason': 'Medical appointment',
        })

        self.assertRedirects(response, reverse('employee_leaves'))
        self.assertFalse(LeaveApplication.objects.filter(employee=self.employee).exists())

    def test_sick_leave_attachment_is_uploaded_and_private(self):
        day = self.next_weekday()
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        with override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(reverse('employee_apply_leave'), {
                'leave_type': 'Sick',
                'half_day_session': 'full',
                'start_date': day.isoformat(),
                'end_date': day.isoformat(),
                'reason': 'Medical appointment',
                'supporting_document': SimpleUploadedFile('certificate.pdf', b'medical certificate', content_type='application/pdf'),
            })
            self.assertRedirects(response, reverse('employee_leaves'))
            application = LeaveApplication.objects.get(employee=self.employee)
            self.assertTrue(application.supporting_document)

            document_response = self.client.get(reverse('employee_leave_document', args=[application.pk]))
            self.assertEqual(document_response.status_code, 200)
            self.assertIn('attachment', document_response['Content-Disposition'])
            document_response.close()

            self.client.force_login(self.colleague)
            denied_response = self.client.get(reverse('employee_leave_document', args=[application.pk]))
            self.assertEqual(denied_response.status_code, 404)

    def test_admin_can_record_approval_and_rejection_feedback(self):
        day = self.next_weekday()
        application = LeaveApplication.objects.create(
            employee=self.employee,
            start_date=day,
            end_date=day,
            reason='Needs review',
        )
        administrator = User.objects.create_user(username='leave-admin', role='admin')
        self.client.force_login(administrator)

        approval_page = self.client.get(reverse('leave_approvals'))
        self.assertContains(approval_page, 'Needs review')
        rejected_without_note = self.client.post(reverse('leave_approvals'), {
            'application_id': application.pk,
            'action': 'reject',
            'approval_notes': '',
        })
        application.refresh_from_db()
        self.assertEqual(application.status, 'pending')

        rejected_with_note = self.client.post(reverse('leave_approvals'), {
            'application_id': application.pk,
            'action': 'reject',
            'approval_notes': 'Please resubmit with dates corrected.',
        })
        self.assertRedirects(rejected_with_note, reverse('leave_approvals'))
        application.refresh_from_db()
        self.assertEqual(application.status, 'rejected')
        self.assertEqual(application.approved_by, administrator)
        self.assertEqual(application.approval_notes, 'Please resubmit with dates corrected.')
        self.client.force_login(self.employee)
        employee_history = self.client.get(reverse('employee_leaves'), {'status': 'rejected'})
        self.assertContains(employee_history, 'leave-admin')
        self.assertContains(employee_history, 'Please resubmit with dates corrected.')

    def test_pending_leave_can_be_withdrawn_only_by_its_owner(self):
        day = self.next_weekday()
        application = LeaveApplication.objects.create(
            employee=self.employee,
            start_date=day,
            end_date=day,
            reason='Pending request',
        )
        response = self.client.post(reverse('employee_withdraw_leave', args=[application.pk]))
        self.assertRedirects(response, reverse('employee_leaves'))
        application.refresh_from_db()
        self.assertEqual(application.status, 'withdrawn')

        another_application = LeaveApplication.objects.create(
            employee=self.employee,
            start_date=day,
            end_date=day,
            reason='Keep private',
        )
        self.client.force_login(self.colleague)
        denied = self.client.post(reverse('employee_withdraw_leave', args=[another_application.pk]))
        self.assertEqual(denied.status_code, 404)
        another_application.refresh_from_db()
        self.assertEqual(another_application.status, 'pending')

    def test_status_filter_search_and_pagination(self):
        day = self.next_weekday()
        for index in range(10):
            LeaveApplication.objects.create(
                employee=self.employee,
                start_date=day,
                end_date=day,
                reason=f'Routine request {index}',
                status='pending' if index < 9 else 'approved',
            )

        first_page = self.client.get(reverse('employee_leaves'), {'status': 'pending'})
        self.assertEqual(first_page.context['leave_applications'].paginator.count, 9)
        self.assertEqual(len(first_page.context['leave_applications'].object_list), 8)
        self.assertTrue(first_page.context['leave_applications'].has_next())

        search_response = self.client.get(reverse('employee_leaves'), {'status': 'approved', 'q': 'Routine request 9'})
        self.assertEqual(search_response.context['leave_applications'].paginator.count, 1)


class EmployeeProjectsTestCase(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(
            username='project-owner',
            first_name='Riley',
            last_name='Jordan',
            role='employee',
        )
        self.team_member = User.objects.create_user(
            username='project-teammate',
            first_name='Sam',
            last_name='Designer',
            role='employee',
            designation='Product Designer',
            manager=self.employee,
        )
        self.client.force_login(self.employee)

    def test_project_portfolio_shows_historical_assignment_and_detail_sections(self):
        project = Project.objects.create(
            name='Client Portal',
            category='Web Platform',
            description='Customer self-service portal',
            objective='Reduce support volume',
            goals='Launch the new account area',
            scope='Authentication and billing',
            start_date=datetime.date(2026, 8, 1),
            end_date=datetime.date(2026, 12, 1),
        )
        project.employees.add(self.team_member)
        ProjectAssignment.objects.create(
            project=project,
            employee=self.employee,
            role='Lead Developer',
            is_active=False,
        )
        ProjectMilestone.objects.create(project=project, title='Design approved', status='done', order=1)
        ProjectMilestone.objects.create(project=project, title='Billing integration', status='in_progress', order=2)
        ProjectTask.objects.create(project=project, employee=self.employee, title='Build account API')
        ProjectTechnology.objects.create(project=project, name='Django')
        ProjectResource.objects.create(
            project=project,
            title='Product brief',
            resource_type='prd',
            url='https://example.com/product-brief',
        )

        response = self.client.get(reverse('employee_projects'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'All Projects')
        self.assertContains(response, 'Active Projects')
        self.assertContains(response, 'Client Portal')
        self.assertContains(response, 'Lead Developer')
        self.assertContains(response, '50%')
        project_data = response.context['project_details'][0]
        self.assertEqual(project_data['objective'], 'Reduce support volume')
        self.assertEqual(project_data['milestones'][0]['status_label'], 'Done')
        self.assertEqual(project_data['tasks'][0]['title'], 'Build account API')
        self.assertEqual(project_data['technologies'], ['Django'])
        self.assertEqual(project_data['resources'][0]['title'], 'Product brief')
        self.assertEqual({member['name'] for member in project_data['team']}, {'Riley Jordan', 'Sam Designer'})

    def test_project_status_filter_limits_cards(self):
        active = Project.objects.create(name='Active Project', status='active')
        active.employees.add(self.employee)
        completed = Project.objects.create(name='Completed Project', status='completed')
        completed.employees.add(self.employee)

        response = self.client.get(reverse('employee_projects'), {'status': 'completed'})

        self.assertContains(response, 'Completed Project')
        self.assertEqual([project['name'] for project in response.context['project_details']], ['Completed Project'])
        self.assertEqual(response.context['selected_filter'], 'completed')

    def test_project_teammates_can_view_each_others_profile_photos(self):
        project = Project.objects.create(name='Shared Project')
        project.employees.add(self.employee, self.team_member)
        photo_url = reverse('employee_photo_by_id', args=[self.team_member.pk])
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        image_data = io.BytesIO()
        Image.new('RGB', (2, 2), color='green').save(image_data, format='PNG')
        photo = SimpleUploadedFile('teammate.png', image_data.getvalue(), content_type='image/png')

        with override_settings(MEDIA_ROOT=media_root):
            self.team_member.profile_photo.save('teammate.png', photo, save=True)
            response = self.client.get(photo_url)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'image/png')
            response.close()


class EmployeeCalendarTestCase(TestCase):
    def setUp(self):
        today = timezone.localdate()
        self.employee = User.objects.create_user(
            username='calendar-user',
            role='employee',
            date_of_birth=datetime.date(1990, today.month, today.day),
        )
        self.colleague = User.objects.create_user(
            username='calendar-colleague',
            first_name='Alex',
            last_name='Team',
            role='employee',
            date_of_birth=datetime.date(1992, today.month, min(today.day + 1, 28)),
        )
        self.client.force_login(self.employee)

    def test_calendar_shows_color_coded_events_and_day_details(self):
        today = timezone.localdate()
        Attendance.objects.create(
            employee=self.employee,
            date=today,
            status='present',
            check_in=datetime.time(9, 0),
            check_out=datetime.time(17, 0),
        )
        CompanyHoliday.objects.create(date=today, name='Company Day')
        LeaveApplication.objects.create(
            employee=self.employee,
            start_date=today,
            end_date=today,
            reason='Calendar leave',
            status='approved',
            leave_type='Casual',
        )
        LeaveApplication.objects.create(
            employee=self.colleague,
            start_date=today,
            end_date=today,
            reason='Team coverage',
            status='approved',
        )

        response = self.client.get(reverse('employee_calendar'), {'month': today.month, 'year': today.year})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'status-present')
        self.assertContains(response, 'status-leave')
        self.assertContains(response, 'status-holiday')
        self.assertContains(response, 'calendar-day-modal')
        self.assertContains(response, 'Check In')
        self.assertContains(response, 'Apply Leave for This Day')
        current_day = next(day for week in response.context['weeks'] for day in week if day and day['date'] == today)
        self.assertEqual(current_day['team_away_count'], 1)

    def test_calendar_week_and_agenda_views(self):
        today = timezone.localdate()
        Attendance.objects.create(employee=self.employee, date=today, status='present')

        week_response = self.client.get(reverse('employee_calendar'), {
            'month': today.month,
            'year': today.year,
            'view': 'week',
        })
        self.assertEqual(week_response.status_code, 200)
        self.assertEqual(len(week_response.context['weeks']), 1)
        self.assertEqual(len(week_response.context['weeks'][0]), 7)

        agenda_response = self.client.get(reverse('employee_calendar'), {
            'month': today.month,
            'year': today.year,
            'view': 'agenda',
        })
        self.assertEqual(agenda_response.status_code, 200)
        agenda_dates = {day['date'] for day in agenda_response.context['agenda_days']}
        self.assertIn(today, agenda_dates)
        self.assertIn(self.colleague.date_of_birth.replace(year=today.year), agenda_dates)

    def test_2026_india_national_holidays_appear_on_calendar(self):
        for month, holiday_name in [(1, 'Republic Day'), (8, 'Independence Day'), (10, 'Gandhi Jayanti')]:
            with self.subTest(holiday=holiday_name):
                response = self.client.get(reverse('employee_calendar'), {'month': month, 'year': 2026})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, holiday_name)
                self.assertContains(response, 'status-holiday')
