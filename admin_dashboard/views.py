import calendar
import datetime
import csv
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.views.generic import ListView, DetailView, TemplateView
from django.db.models import Q, Count
from django.http import FileResponse, Http404, HttpResponse
from django.contrib.auth.views import LoginView
from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, UpdateView
from django.utils import timezone
from core.models import (
    User,
    Attendance,
    AttendanceCorrectionRequest,
    WorkLog,
    LeaveApplication,
    LeavePolicy,
    CompanyHoliday,
    Salary,
    SalaryComponent,
    SalaryStructure,
    SalaryRevision,
    Department,
    Designation,
    EmployeeDocument,
    EmployeeActivity,
)
from core.views import (
    build_salary_payslip,
    get_leave_units,
    get_salary_attendance_summary,
    get_salary_breakdown,
    send_leave_status_email,
)
from core.permissions import AdminRoleRequiredMixin
from .forms import (
    DepartmentForm,
    DesignationForm,
    EmployeeDocumentForm,
    EmployeeManagementForm,
    LeavePolicyForm,
    SalaryStructureForm,
)

class RootRedirectView(View):
    """
    Opens the login page whenever the site root is visited.
    """
    def get(self, request):
        return redirect('login')


class AdminDashboardView(AdminRoleRequiredMixin, TemplateView):
    template_name = 'admin_dashboard/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        now = timezone.now()
        all_employees = User.objects.filter(role='employee')
        employees = all_employees.filter(is_active=True)
        today_attendance = Attendance.objects.filter(employee__in=employees, date=today)

        today_counts = today_attendance.aggregate(
            present=Count('id', filter=Q(status='present')),
            absent=Count('id', filter=Q(status='absent')),
            leave=Count('id', filter=Q(status='leave')),
            half_day=Count('id', filter=Q(status='half_day')),
        )
        approved_leave_ids = set(
            LeaveApplication.objects.filter(
                employee__in=employees,
                status='approved',
                start_date__lte=today,
                end_date__gte=today,
            ).values_list('employee_id', flat=True)
        )
        attendance_by_employee = {
            row['employee_id']: row['status']
            for row in today_attendance.values('employee_id', 'status')
        }
        on_leave_ids = {
            employee_id
            for employee_id in approved_leave_ids
            if employee_id not in attendance_by_employee
        }
        on_leave_ids.update(
            employee_id
            for employee_id, status in attendance_by_employee.items()
            if status == 'leave'
        )
        employees_on_leave = len(on_leave_ids)

        current_month_start = today.replace(day=1)
        current_month_attendance = Attendance.objects.filter(
            employee__in=employees,
            date__gte=current_month_start,
            date__lte=today,
            status__in=['present', 'half_day', 'absent'],
        ).aggregate(
            present=Count('id', filter=Q(status='present')),
            half_day=Count('id', filter=Q(status='half_day')),
            absent=Count('id', filter=Q(status='absent')),
        )
        recorded_days = (
            current_month_attendance['present']
            + current_month_attendance['half_day']
            + current_month_attendance['absent']
        )
        attendance_percentage = (
            round(
                (
                    current_month_attendance['present']
                    + current_month_attendance['half_day'] * 0.5
                )
                / recorded_days
                * 100,
                1,
            )
            if recorded_days
            else None
        )

        department_attendance = (
            Attendance.objects.filter(
                employee__in=employees,
                date__gte=current_month_start,
                date__lte=today,
                status__in=['present', 'half_day', 'absent'],
            )
            .exclude(employee__department__isnull=True)
            .exclude(employee__department='')
            .values('employee__department')
            .annotate(
                present=Count('id', filter=Q(status='present')),
                half_day=Count('id', filter=Q(status='half_day')),
                absent=Count('id', filter=Q(status='absent')),
            )
            .order_by('employee__department')
        )
        department_attendance_summary = []
        for department in department_attendance:
            total = department['present'] + department['half_day'] + department['absent']
            department_attendance_summary.append({
                'name': department['employee__department'],
                'percentage': round(
                    (department['present'] + department['half_day'] * 0.5) / total * 100,
                    1,
                ) if total else None,
                'recorded_days': total,
            })
        employee_attendance_summary = []
        employee_attendance = (
            Attendance.objects.filter(
                employee__in=employees,
                date__gte=current_month_start,
                date__lte=today,
                status__in=['present', 'half_day', 'absent'],
            )
            .values(
                'employee_id',
                'employee__first_name',
                'employee__last_name',
                'employee__username',
            )
            .annotate(
                present=Count('id', filter=Q(status='present')),
                half_day=Count('id', filter=Q(status='half_day')),
                absent=Count('id', filter=Q(status='absent')),
            )
        )
        for employee_record in employee_attendance:
            total = (
                employee_record['present']
                + employee_record['half_day']
                + employee_record['absent']
            )
            first_name = employee_record['employee__first_name']
            last_name = employee_record['employee__last_name']
            employee_attendance_summary.append({
                'employee_id': employee_record['employee_id'],
                'name': f'{first_name} {last_name}'.strip()
                or employee_record['employee__username'],
                'percentage': round(
                    (
                        employee_record['present']
                        + employee_record['half_day'] * 0.5
                    )
                    / total
                    * 100,
                    1,
                ) if total else None,
                'recorded_days': total,
            })
        employee_attendance_summary.sort(
            key=lambda item: (item['percentage'] is None, item['percentage'] or 0)
        )

        pending_applications = LeaveApplication.objects.filter(status='pending').select_related(
            'employee', 'employee__manager', 'handover_contact'
        )
        pending_count = pending_applications.count()
        pending_applications = pending_applications.order_by('start_date', 'applied_on')[:5]

        department_count = (
            employees.exclude(department__isnull=True)
            .exclude(department='')
            .values('department')
            .distinct()
            .count()
        )
        department_distribution = list(
            employees.exclude(department__isnull=True)
            .exclude(department='')
            .values('department')
            .annotate(employee_count=Count('id'))
            .order_by('-employee_count', 'department')
        )

        month_starts = []
        for offset in range(11, -1, -1):
            month_index = today.year * 12 + today.month - 1 - offset
            year, zero_based_month = divmod(month_index, 12)
            month_starts.append(datetime.date(year, zero_based_month + 1, 1))
        chart_start = month_starts[0]
        attendance_by_month = {
            (row['date__year'], row['date__month']): row
            for row in Attendance.objects.filter(
                employee__in=employees,
                date__gte=chart_start,
                date__lte=today,
            )
            .values('date__year', 'date__month')
            .annotate(
                present=Count('id', filter=Q(status='present')),
                absent=Count('id', filter=Q(status='absent')),
                leave=Count('id', filter=Q(status='leave')),
                half_day=Count('id', filter=Q(status='half_day')),
            )
        }
        hiring_by_month = {
            (row['joining_date__year'], row['joining_date__month']): row['employee_count']
            for row in all_employees.filter(
                joining_date__gte=chart_start,
                joining_date__lte=today,
            )
            .values('joining_date__year', 'joining_date__month')
            .annotate(employee_count=Count('id'))
        }
        month_labels = [month.strftime('%b %Y') for month in month_starts]
        attendance_trend = {
            'labels': month_labels,
            'present': [],
            'absent': [],
            'leave': [],
        }
        hiring_trend = {'labels': month_labels, 'values': []}
        for month in month_starts:
            attendance_month = attendance_by_month.get((month.year, month.month), {})
            attendance_trend['present'].append(attendance_month.get('present', 0))
            attendance_trend['absent'].append(attendance_month.get('absent', 0))
            attendance_trend['leave'].append(attendance_month.get('leave', 0))
            hiring_trend['values'].append(hiring_by_month.get((month.year, month.month), 0))

        birthday_cutoff = today + datetime.timedelta(days=30)
        upcoming_birthdays = []
        upcoming_anniversaries = []
        for employee in employees.filter(
            Q(date_of_birth__isnull=False) | Q(joining_date__isnull=False)
        ).only('id', 'first_name', 'last_name', 'username', 'date_of_birth', 'joining_date'):
            if employee.date_of_birth:
                birthday = self._next_occurrence(
                    employee.date_of_birth.month, employee.date_of_birth.day, today
                )
                if birthday <= birthday_cutoff:
                    upcoming_birthdays.append({
                        'employee': employee,
                        'date': birthday,
                        'days_until': (birthday - today).days,
                    })
            if employee.joining_date:
                anniversary = self._next_occurrence(
                    employee.joining_date.month, employee.joining_date.day, today
                )
                if (
                    employee.joining_date.year < anniversary.year
                    and anniversary <= birthday_cutoff
                ):
                    upcoming_anniversaries.append({
                        'employee': employee,
                        'date': anniversary,
                        'years': anniversary.year - employee.joining_date.year,
                        'days_until': (anniversary - today).days,
                    })
        upcoming_birthdays.sort(key=lambda item: (item['date'], item['employee'].username))
        upcoming_anniversaries.sort(key=lambda item: (item['date'], item['employee'].username))

        new_joiners = employees.filter(
            joining_date__year=today.year,
            joining_date__month=today.month,
            joining_date__lte=today,
        ).order_by('-joining_date', 'first_name', 'last_name')[:5]

        activity_cutoff = today - datetime.timedelta(days=30)
        activity_cutoff_datetime = timezone.make_aware(
            datetime.datetime.combine(activity_cutoff, datetime.time.min)
        )
        recent_activities = []
        for record in Attendance.objects.filter(
            employee__in=employees,
            date__gte=activity_cutoff,
            date__lte=today,
        ).select_related('employee').order_by('-date')[:5]:
            recent_activities.append({
                'occurred_at': timezone.make_aware(
                    datetime.datetime.combine(record.date, datetime.time.min)
                ),
                'title': 'Attendance recorded',
                'description': f'{record.employee.get_full_name() or record.employee.username} · {record.get_status_display()}',
                'employee_id': record.employee_id,
                'icon': 'bi-calendar-check',
            })
        for record in WorkLog.objects.filter(
            employee__in=employees,
            date__gte=activity_cutoff,
            date__lte=today,
        ).select_related('employee').order_by('-date', '-start_time')[:5]:
            recent_activities.append({
                'occurred_at': timezone.make_aware(
                    datetime.datetime.combine(record.date, record.start_time)
                ),
                'title': 'Work log submitted',
                'description': f'{record.employee.get_full_name() or record.employee.username} · {record.category}',
                'employee_id': record.employee_id,
                'icon': 'bi-journal-text',
            })
        for record in LeaveApplication.objects.filter(
            employee__in=employees,
            applied_on__gte=activity_cutoff_datetime,
            applied_on__lte=now,
        ).select_related('employee').order_by('-applied_on')[:5]:
            recent_activities.append({
                'occurred_at': record.applied_on,
                'title': 'Leave request submitted',
                'description': f'{record.employee.get_full_name() or record.employee.username} · {record.leave_type}',
                'employee_id': record.employee_id,
                'icon': 'bi-calendar2-week',
            })
        for record in AttendanceCorrectionRequest.objects.filter(
            employee__in=employees,
            created_at__gte=activity_cutoff_datetime,
            created_at__lte=now,
        ).select_related('employee').order_by('-created_at')[:5]:
            recent_activities.append({
                'occurred_at': record.created_at,
                'title': 'Attendance correction requested',
                'description': f'{record.employee.get_full_name() or record.employee.username} · {record.date:%b %d}',
                'employee_id': record.employee_id,
                'icon': 'bi-clock-history',
            })
        for employee in employees.filter(
            date_joined__gte=activity_cutoff_datetime,
            date_joined__lte=now,
        ).order_by('-date_joined')[:5]:
            recent_activities.append({
                'occurred_at': employee.date_joined,
                'title': 'Employee account created',
                'description': employee.get_full_name() or employee.username,
                'employee_id': employee.id,
                'icon': 'bi-person-plus',
            })
        recent_activities.sort(key=lambda item: item['occurred_at'], reverse=True)

        recent_notifications = []
        for record in LeaveApplication.objects.filter(
            employee__in=employees,
            status='pending',
        ).select_related('employee').order_by('-applied_on')[:5]:
            recent_notifications.append({
                'created_at': record.applied_on,
                'title': 'Leave request needs review',
                'description': f'{record.employee.get_full_name() or record.employee.username} · {record.leave_type}',
                'url_name': 'leave_approvals',
                'icon': 'bi-exclamation-circle',
            })
        for record in AttendanceCorrectionRequest.objects.filter(
            employee__in=employees,
            status='pending',
        ).select_related('employee').order_by('-created_at')[:5]:
            recent_notifications.append({
                'created_at': record.created_at,
                'title': 'Attendance correction requested',
                'description': f'{record.employee.get_full_name() or record.employee.username} · {record.date:%b %d}',
                'url_name': 'attendance_management',
                'icon': 'bi-clock-history',
            })
        recent_notifications.sort(key=lambda item: item['created_at'], reverse=True)

        context.update({
            'today': today,
            'employee_count': employees.count(),
            'total_employee_count': all_employees.count(),
            'active_employee_count': employees.count(),
            'present_count': today_counts['present'],
            'absent_count': today_counts['absent'],
            'employees_on_leave': employees_on_leave,
            'late_arrival_count': today_attendance.filter(
                check_in__gt=datetime.time(9, 15)
            ).count(),
            'half_day_count': today_counts['half_day'],
            'pending_leave_count': pending_count,
            'pending_applications': pending_applications,
            'new_joiner_count': employees.filter(
                joining_date__year=today.year,
                joining_date__month=today.month,
                joining_date__lte=today,
            ).count(),
            'new_joiners': new_joiners,
            'department_count': department_count,
            'attendance_percentage': attendance_percentage,
            'department_attendance_summary': department_attendance_summary,
            'employee_attendance_summary': employee_attendance_summary[:10],
            'department_distribution': department_distribution,
            'attendance_day_chart': {
                'labels': ['Present', 'Absent', 'On leave', 'Half day'],
                'values': [
                    today_counts['present'],
                    today_counts['absent'],
                    employees_on_leave,
                    today_counts['half_day'],
                ],
            },
            'attendance_trend_chart': attendance_trend,
            'hiring_trend_chart': hiring_trend,
            'upcoming_birthdays': upcoming_birthdays[:5],
            'upcoming_anniversaries': upcoming_anniversaries[:5],
            'recent_activities': recent_activities[:8],
            'recent_notifications': recent_notifications[:8],
        })
        return context

    @staticmethod
    def _next_occurrence(month, day, reference_date):
        year = reference_date.year
        while True:
            occurrence = datetime.date(
                year,
                month,
                min(day, calendar.monthrange(year, month)[1]),
            )
            if occurrence >= reference_date:
                return occurrence
            year += 1


class EmployeeListView(AdminRoleRequiredMixin, ListView):
    """
    Paginated employee directory with validated search, filters, and sorting.
    Restricted to admin users.
    """
    model = User
    template_name = 'admin_dashboard/employee_list.html'
    context_object_name = 'employees'
    paginate_by = 15
    SORT_FIELDS = {
        'name': ('first_name', 'last_name', 'username'),
        'employee_id': ('employee_id',),
        'department': ('department', 'first_name', 'last_name'),
        'designation': ('designation', 'first_name', 'last_name'),
        'joining_date': ('joining_date',),
        'status': ('employment_status', 'first_name', 'last_name'),
    }

    def get_queryset(self):
        queryset = User.objects.filter(role='employee').select_related('manager')

        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(personal_email__icontains=search_query) |
                Q(employee_id__icontains=search_query)
            )

        department = self.request.GET.get('department', '').strip()
        if department:
            queryset = queryset.filter(department__iexact=department)

        status = self.request.GET.get('status', '').strip()
        if status in dict(User.EMPLOYMENT_STATUS_CHOICES):
            queryset = queryset.filter(employment_status=status)

        account_status = self.request.GET.get('account_status', '').strip()
        if account_status == 'active':
            queryset = queryset.filter(is_active=True)
        elif account_status == 'deactivated':
            queryset = queryset.filter(is_active=False)

        sort = self.request.GET.get('sort', 'name').strip()
        if sort not in self.SORT_FIELDS:
            sort = 'name'
        direction = self.request.GET.get('direction', 'asc').strip().lower()
        if direction not in {'asc', 'desc'}:
            direction = 'asc'
        ordering = self.SORT_FIELDS[sort]
        if direction == 'desc':
            ordering = tuple(f'-{field}' for field in ordering)
        return queryset.order_by(*ordering, 'pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee_queryset = User.objects.filter(role='employee')
        context['departments'] = (
            employee_queryset.exclude(department__isnull=True)
            .exclude(department='')
            .values_list('department', flat=True)
            .distinct()
            .order_by('department')
        )
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_department'] = self.request.GET.get('department', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_account_status'] = self.request.GET.get('account_status', '')
        context['sort'] = self.request.GET.get('sort', 'name')
        context['direction'] = self.request.GET.get('direction', 'asc')
        context['next_sort_directions'] = {
            sort: (
                'desc'
                if context['sort'] == sort and context['direction'] == 'asc'
                else 'asc'
            )
            for sort in self.SORT_FIELDS
        }
        context['employment_statuses'] = User.EMPLOYMENT_STATUS_CHOICES
        context['employee_total'] = employee_queryset.count()
        return context


class EmployeeDetailView(AdminRoleRequiredMixin, DetailView):
    """
    Detail page for an employee (Admin only). Shows profile details,
    monthly attendance metrics using ORM aggregation, date-filtered work logs,
    and leave/salary payment summaries.
    """
    model = User
    template_name = 'admin_dashboard/employee_detail.html'
    context_object_name = 'employee'

    def get_queryset(self):
        return User.objects.filter(role='employee').select_related('manager')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.object
        today = timezone.localdate()
        
        # 1. ORM Aggregation: Group attendance by month & year, count statuses
        attendance_stats = Attendance.objects.filter(employee=employee).values(
            'date__year', 'date__month'
        ).annotate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present')),
            half_day=Count('id', filter=Q(status='half_day')),
            absent=Count('id', filter=Q(status='absent')),
            leave=Count('id', filter=Q(status='leave'))
        ).order_by('-date__year', '-date__month')
        
        # Calculate percentage for each month
        monthly_attendance_summary = []
        for stat in attendance_stats:
            total = stat['total']
            present = stat['present']
            half_day = stat['half_day']
            
            # Count present and half_day (half_day counts as 0.5)
            active_days = present + (0.5 * half_day)
            percentage = round((active_days / total) * 100, 2) if total > 0 else 0.00
            
            month_name = datetime.date(1900, stat['date__month'], 1).strftime('%B')
            
            monthly_attendance_summary.append({
                'year': stat['date__year'],
                'month': stat['date__month'],
                'month_name': month_name,
                'total': total,
                'present': present,
                'half_day': half_day,
                'absent': stat['absent'],
                'leave': stat['leave'],
                'percentage': percentage,
            })
            
        daily_attendance = Attendance.objects.filter(employee=employee).order_by('-date')
            
        # 2. Work log history (with date range filtering)
        work_logs = WorkLog.objects.filter(employee=employee).order_by('-date')
        
        start_date_str = self.request.GET.get('worklog_start', '').strip()
        end_date_str = self.request.GET.get('worklog_end', '').strip()
        
        if start_date_str:
            try:
                start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                work_logs = work_logs.filter(date__gte=start_date)
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
                work_logs = work_logs.filter(date__lte=end_date)
            except ValueError:
                pass
                
        # 3. Leave history splits
        # Leaves already taken: approved and ended in the past (end_date < today)
        taken_leaves = LeaveApplication.objects.filter(
            employee=employee,
            status='approved',
            end_date__lt=today
        ).order_by('-start_date')
        
        # Pending + currently active/future approved leaves
        active_leaves = LeaveApplication.objects.filter(employee=employee).filter(
            Q(status='pending') | Q(status='approved', end_date__gte=today)
        ).order_by('-start_date')
        
        # 4. Salary history & next calculation
        next_salary_due = employee.get_next_salary_due_date()
        salary_history = Salary.objects.filter(employee=employee).order_by('-year', '-month')
        
        # Fetch current month's status
        current_month_status = Salary.objects.filter(
            employee=employee,
            month=today.month,
            year=today.year
        ).first()
        
        context.update({
            'monthly_attendance_summary': monthly_attendance_summary,
            'daily_attendance': daily_attendance,
            'work_logs': work_logs,
            'worklog_start': start_date_str,
            'worklog_end': end_date_str,
            'taken_leaves': taken_leaves,
            'active_leaves': active_leaves,
            'next_salary_due': next_salary_due,
            'salary_history': salary_history,
            'current_month_status': current_month_status,
            'today': today,
            'documents': EmployeeDocument.objects.filter(employee=employee).order_by(
                '-uploaded_at'
            ),
            'document_form': EmployeeDocumentForm(),
            'activity_timeline': self._build_activity_timeline(employee),
        })
        return context

    @staticmethod
    def _build_activity_timeline(employee):
        timeline = []
        for attendance in employee.attendances.order_by('-date')[:10]:
            timeline.append({
                'occurred_at': timezone.make_aware(
                    datetime.datetime.combine(attendance.date, datetime.time.min)
                ),
                'title': 'Attendance recorded',
                'description': f'{attendance.get_status_display()}'
                + (f' · Check-in {attendance.check_in:%H:%M}' if attendance.check_in else ''),
                'icon': 'bi-calendar-check',
            })
        for work_log in employee.work_logs.order_by('-date', '-start_time')[:10]:
            timeline.append({
                'occurred_at': timezone.make_aware(
                    datetime.datetime.combine(work_log.date, work_log.start_time)
                ),
                'title': 'Work log submitted',
                'description': f'{work_log.category} · {work_log.hours_worked or 0} hours',
                'icon': 'bi-journal-text',
            })
        for leave in employee.leave_applications.order_by('-applied_on')[:10]:
            timeline.append({
                'occurred_at': leave.applied_on,
                'title': f'Leave request {leave.status}',
                'description': f'{leave.leave_type} · {leave.start_date:%b %d, %Y} to {leave.end_date:%b %d, %Y}',
                'icon': 'bi-calendar2-week',
            })
        for correction in employee.attendance_corrections.order_by('-created_at')[:10]:
            timeline.append({
                'occurred_at': correction.created_at,
                'title': f'Attendance correction {correction.status}',
                'description': f'{correction.date:%b %d, %Y} · {correction.reason}',
                'icon': 'bi-clock-history',
            })
        for activity in employee.management_activities.select_related('actor')[:25]:
            timeline.append({
                'occurred_at': activity.created_at,
                'title': activity.get_activity_type_display(),
                'description': activity.description
                or (
                    f'By {activity.actor.get_full_name() or activity.actor.username}'
                    if activity.actor else 'Administrative action'
                ),
                'icon': {
                    'created': 'bi-person-plus',
                    'updated': 'bi-pencil-square',
                    'status_changed': 'bi-arrow-left-right',
                    'deactivated': 'bi-person-dash',
                    'reactivated': 'bi-person-check',
                    'document_uploaded': 'bi-file-earmark-arrow-up',
                    'document_deleted': 'bi-file-earmark-x',
                }.get(activity.activity_type, 'bi-clock-history'),
            })
        if not employee.management_activities.exists():
            timeline.append({
                'occurred_at': employee.date_joined,
                'title': 'Employee account created',
                'description': f'Employee ID {employee.employee_id or "pending"}',
                'icon': 'bi-person-plus',
            })
        timeline.sort(key=lambda entry: entry['occurred_at'], reverse=True)
        return timeline[:25]


class EmployeeCreateView(AdminRoleRequiredMixin, CreateView):
    model = User
    form_class = EmployeeManagementForm
    template_name = 'admin_dashboard/employee_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        EmployeeActivity.objects.create(
            employee=self.object,
            actor=self.request.user,
            activity_type='created',
            description=f'Employee profile created with ID {self.object.employee_id}.',
        )
        messages.success(
            self.request,
            f'Employee {self.object.get_full_name() or self.object.username} was created.',
        )
        return response

    def get_success_url(self):
        return reverse('employee_detail', kwargs={'pk': self.object.pk})


class EmployeeUpdateView(AdminRoleRequiredMixin, UpdateView):
    model = User
    form_class = EmployeeManagementForm
    template_name = 'admin_dashboard/employee_form.html'

    def get_queryset(self):
        return User.objects.filter(role='employee')

    def form_valid(self, form):
        previous_status = User.objects.values_list(
            'employment_status', flat=True
        ).get(pk=self.object.pk)
        changed_data = set(form.changed_data)
        response = super().form_valid(form)
        if changed_data:
            EmployeeActivity.objects.create(
                employee=self.object,
                actor=self.request.user,
                activity_type='updated',
                description='Employee personal or professional profile details updated.',
            )
        if previous_status != self.object.employment_status:
            EmployeeActivity.objects.create(
                employee=self.object,
                actor=self.request.user,
                activity_type='status_changed',
                description=(
                    f'Employment status changed from {previous_status.replace("_", " ").title()} '
                    f'to {self.object.get_employment_status_display()}.'
                ),
            )
        messages.success(
            self.request,
            f'Employee {self.object.get_full_name() or self.object.username} was updated.',
        )
        return response

    def get_success_url(self):
        return reverse('employee_detail', kwargs={'pk': self.object.pk})


class EmployeeDeactivateView(AdminRoleRequiredMixin, View):
    def post(self, request, pk):
        employee = get_object_or_404(User, pk=pk, role='employee', is_active=True)
        employee.is_active = False
        employee.save(update_fields=['is_active'])
        EmployeeActivity.objects.create(
            employee=employee,
            actor=request.user,
            activity_type='deactivated',
            description='Sign-in access was disabled by an administrator.',
        )
        messages.success(
            request,
            f'{employee.get_full_name() or employee.username} can no longer sign in.',
        )
        return redirect('employee_detail', pk=employee.pk)


class EmployeeActivateView(AdminRoleRequiredMixin, View):
    def post(self, request, pk):
        employee = get_object_or_404(User, pk=pk, role='employee', is_active=False)
        if employee.employment_status not in {'active', 'on_leave'}:
            messages.error(
                request,
                'Change the employment status to Active or On Leave before restoring account access.',
            )
            return redirect('employee_detail', pk=employee.pk)
        employee.is_active = True
        employee.save(update_fields=['is_active'])
        EmployeeActivity.objects.create(
            employee=employee,
            actor=request.user,
            activity_type='reactivated',
            description='Sign-in access was restored by an administrator.',
        )
        messages.success(
            request,
            f'{employee.get_full_name() or employee.username} can sign in again.',
        )
        return redirect('employee_detail', pk=employee.pk)


class EmployeeDocumentUploadView(AdminRoleRequiredMixin, View):
    def post(self, request, pk):
        employee = get_object_or_404(User, pk=pk, role='employee')
        form = EmployeeDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.employee = employee
            document.save()
            EmployeeActivity.objects.create(
                employee=employee,
                actor=request.user,
                activity_type='document_uploaded',
                description=f'{document.title} · {document.get_category_display()}',
            )
            messages.success(request, 'Employee document uploaded successfully.')
        else:
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)
        return redirect('employee_detail', pk=employee.pk)


class EmployeeDocumentDownloadView(AdminRoleRequiredMixin, View):
    def get(self, request, pk, document_pk):
        document = get_object_or_404(
            EmployeeDocument.objects.select_related('employee'),
            pk=document_pk,
            employee_id=pk,
            employee__role='employee',
        )
        if not document.file:
            raise Http404('This employee document has no file.')
        return FileResponse(
            document.file.open('rb'),
            as_attachment=True,
            filename=Path(document.file.name).name,
            content_type='application/octet-stream',
        )


class EmployeeDocumentDeleteView(AdminRoleRequiredMixin, View):
    def post(self, request, pk, document_pk):
        document = get_object_or_404(
            EmployeeDocument.objects.select_related('employee'),
            pk=document_pk,
            employee_id=pk,
            employee__role='employee',
        )
        employee_id = document.employee_id
        EmployeeActivity.objects.create(
            employee=document.employee,
            actor=request.user,
            activity_type='document_deleted',
            description=f'{document.title} was removed.',
        )
        document.file.delete(save=False)
        document.delete()
        messages.success(request, 'Employee document deleted successfully.')
        return redirect('employee_detail', pk=employee_id)


class DepartmentManagementView(AdminRoleRequiredMixin, View):
    template_name = 'admin_dashboard/organization.html'

    def get(self, request):
        department = get_object_or_404(
            Department,
            pk=request.GET['department'],
        ) if request.GET.get('department', '').isdigit() else None
        designation = get_object_or_404(
            Designation.objects.select_related('department'),
            pk=request.GET['designation'],
        ) if request.GET.get('designation', '').isdigit() else None
        departments = Department.objects.annotate(
            employee_count=Count(
                'employees',
                filter=Q(employees__role='employee', employees__is_active=True),
            ),
        ).select_related('head', 'parent_department').prefetch_related('designations')
        return render(request, self.template_name, {
            'departments': departments,
            'designations': Designation.objects.select_related('department').annotate(
                employee_count=Count(
                    'employees',
                    filter=Q(employees__role='employee', employees__is_active=True),
                ),
            ),
            'department_form': DepartmentForm(instance=department),
            'designation_form': DesignationForm(instance=designation),
            'editing_department': department,
            'editing_designation': designation,
        })

    @transaction.atomic
    def post(self, request):
        action = request.POST.get('action')
        if action == 'department':
            department_id = request.POST.get('department_id')
            department = get_object_or_404(Department, pk=department_id) if department_id else None
            previous_name = department.name if department else None
            form = DepartmentForm(request.POST, instance=department)
            if form.is_valid():
                department = form.save()
                if previous_name and previous_name != department.name:
                    User.objects.filter(department_record=department).update(
                        department=department.name,
                    )
                if department.head and department.head.department_record_id is None:
                    department.head.department_record = department
                    department.head.department = department.name
                    head_update_fields = ['department_record', 'department']
                    if (
                        department.head.designation_record_id
                        and department.head.designation_record.department_id != department.pk
                    ):
                        department.head.designation_record = None
                        department.head.designation = ''
                        head_update_fields.extend(['designation_record', 'designation'])
                    department.head.save(update_fields=head_update_fields)
                messages.success(request, 'Department saved.')
            else:
                messages.error(request, 'Correct the department fields and try again.')
                return render(request, self.template_name, self._context(department_form=form))
        elif action == 'designation':
            designation_id = request.POST.get('designation_id')
            designation = get_object_or_404(Designation, pk=designation_id) if designation_id else None
            previous_name = designation.name if designation else None
            form = DesignationForm(request.POST, instance=designation)
            if form.is_valid():
                designation = form.save()
                if previous_name and previous_name != designation.name:
                    User.objects.filter(designation_record=designation).update(
                        designation=designation.name,
                    )
                messages.success(request, 'Designation saved.')
            else:
                messages.error(request, 'Correct the designation fields and try again.')
                return render(request, self.template_name, self._context(designation_form=form))
        else:
            messages.error(request, 'Choose a valid organization action.')
        return redirect('organization_management')

    def _context(self, department_form=None, designation_form=None):
        departments = Department.objects.annotate(
            employee_count=Count(
                'employees',
                filter=Q(employees__role='employee', employees__is_active=True),
            ),
        ).select_related('head', 'parent_department').prefetch_related('designations')
        return {
            'departments': departments,
            'designations': Designation.objects.select_related('department').annotate(
                employee_count=Count(
                    'employees',
                    filter=Q(employees__role='employee', employees__is_active=True),
                ),
            ),
            'department_form': department_form or DepartmentForm(),
            'designation_form': designation_form or DesignationForm(),
        }


class SalaryStructureManagementView(AdminRoleRequiredMixin, View):
    template_name = 'admin_dashboard/salary_structure_form.html'

    def get(self, request, pk=None):
        structure = get_object_or_404(
            SalaryStructure.objects.select_related('employee'),
            pk=pk,
        ) if pk else None
        return render(request, self.template_name, {
            'form': SalaryStructureForm(instance=structure),
            'structure': structure,
            'revisions': structure.revisions.select_related('revised_by') if structure else [],
        })

    @transaction.atomic
    def post(self, request, pk=None):
        structure = get_object_or_404(SalaryStructure, pk=pk) if pk else None
        form = SalaryStructureForm(request.POST, instance=structure)
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form,
                'structure': structure,
                'revisions': structure.revisions.select_related('revised_by') if structure else [],
            })
        reason = form.cleaned_data['reason']
        structure = form.save()
        if structure.effective_from <= timezone.localdate():
            structure.employee.salary_amount = structure.gross_salary
            structure.employee.save(update_fields=['salary_amount'])
        SalaryRevision.objects.create(
            structure=structure,
            basic_salary=structure.basic_salary,
            hra=structure.hra,
            allowances=structure.allowances,
            deductions=structure.deductions,
            attendance_based=structure.attendance_based,
            effective_from=structure.effective_from,
            reason=reason,
            revised_by=request.user,
        )
        messages.success(request, 'Salary structure saved and revision recorded.')
        return redirect('payroll_management')


def _period_workdays(start_date, end_date, holidays):
    current_date = start_date
    count = 0
    while current_date <= end_date:
        if current_date.weekday() < 5 and current_date not in holidays:
            count += 1
        current_date += datetime.timedelta(days=1)
    return count


def _create_monthly_salary(employee, structure_revision, year, month, month_start, month_end, holidays):
    month_workdays = _period_workdays(month_start, month_end, holidays)
    eligible_start = max(
        month_start,
        structure_revision.effective_from,
        employee.joining_date or month_start,
    )
    eligible_workdays = _period_workdays(eligible_start, month_end, holidays)
    if not month_workdays or not eligible_workdays:
        return None

    unpaid_by_date = {}
    if structure_revision.attendance_based:
        leave_policies = {
            policy.leave_type: policy.is_paid
            for policy in LeavePolicy.objects.all()
        }
        paid_leave_types = [
            leave_type
            for leave_type, _ in LeaveApplication.LEAVE_TYPE_CHOICES
            if leave_policies.get(leave_type, leave_type != 'Unpaid')
        ]
        unpaid_leave_types = [
            leave_type
            for leave_type, _ in LeaveApplication.LEAVE_TYPE_CHOICES
            if not leave_policies.get(leave_type, leave_type != 'Unpaid')
        ]
        paid_leave_dates = set()
        paid_leaves = LeaveApplication.objects.filter(
            employee=employee,
            status='approved',
            leave_type__in=paid_leave_types,
            start_date__lte=month_end,
            end_date__gte=eligible_start,
        )
        for leave in paid_leaves:
            current_date = max(leave.start_date, eligible_start)
            last_date = min(leave.end_date, month_end)
            while current_date <= last_date:
                if current_date.weekday() < 5 and current_date not in holidays:
                    paid_leave_dates.add(current_date)
                current_date += datetime.timedelta(days=1)
        for attendance in Attendance.objects.filter(
            employee=employee,
            date__range=(eligible_start, month_end),
            status__in=['absent', 'half_day'],
        ):
            if (
                attendance.date.weekday() < 5
                and attendance.date not in holidays
                and attendance.date not in paid_leave_dates
            ):
                unpaid_by_date[attendance.date] = Decimal('1') if attendance.status == 'absent' else Decimal('0.5')
        unpaid_leaves = LeaveApplication.objects.filter(
            employee=employee,
            status='approved',
            leave_type__in=unpaid_leave_types,
            start_date__lte=month_end,
            end_date__gte=eligible_start,
        )
        for leave in unpaid_leaves:
            current_date = max(leave.start_date, eligible_start)
            last_date = min(leave.end_date, month_end)
            while current_date <= last_date:
                if current_date.weekday() < 5 and current_date not in holidays:
                    amount = Decimal('0.5') if (
                        leave.half_day_session != 'full'
                        and leave.start_date == leave.end_date == current_date
                    ) else Decimal('1')
                    unpaid_by_date[current_date] = max(
                        unpaid_by_date.get(current_date, Decimal('0')),
                        amount,
                    )
                current_date += datetime.timedelta(days=1)
    unpaid_units = min(
        Decimal(eligible_workdays),
        sum(unpaid_by_date.values(), Decimal('0')),
    )
    period_factor = Decimal(eligible_workdays) / Decimal(month_workdays)
    money = Decimal('0.01')
    basic = (structure_revision.basic_salary * period_factor).quantize(money, rounding=ROUND_HALF_UP)
    hra = (structure_revision.hra * period_factor).quantize(money, rounding=ROUND_HALF_UP)
    allowances = (structure_revision.allowances * period_factor).quantize(money, rounding=ROUND_HALF_UP)
    fixed_deductions = (
        structure_revision.deductions * period_factor
    ).quantize(money, rounding=ROUND_HALF_UP)
    unpaid_deduction = (
        structure_revision.basic_salary
        + structure_revision.hra
        + structure_revision.allowances
    ) * unpaid_units / Decimal(month_workdays)
    unpaid_deduction = unpaid_deduction.quantize(money, rounding=ROUND_HALF_UP)
    gross = basic + hra + allowances
    fixed_deductions = min(fixed_deductions, gross)
    unpaid_deduction = min(unpaid_deduction, max(Decimal('0'), gross - fixed_deductions))
    total_deductions = fixed_deductions + unpaid_deduction
    net_pay = gross - total_deductions

    salary = Salary.objects.create(
        employee=employee,
        month=month,
        year=year,
        amount=net_pay,
        status='pending',
        remarks=(
            f'Generated from salary structure effective {structure_revision.effective_from}. '
            f'Attendance-based pro-rating {"enabled" if structure_revision.attendance_based else "disabled"}.'
        ),
    )
    for name, amount in (
        ('Basic Salary', basic),
        ('HRA', hra),
        ('Allowances', allowances),
    ):
        SalaryComponent.objects.create(
            salary=salary,
            component_type='earning',
            name=name,
            amount=amount,
        )
    if fixed_deductions:
        SalaryComponent.objects.create(
            salary=salary,
            component_type='deduction',
            name='Other Deductions',
            amount=fixed_deductions,
            formula=f'Monthly deductions pro-rated for {eligible_workdays}/{month_workdays} scheduled workdays',
        )
    if unpaid_deduction:
        SalaryComponent.objects.create(
            salary=salary,
            component_type='deduction',
            name='Unpaid / Absence Adjustment',
            amount=unpaid_deduction,
            formula=f'{unpaid_units} unpaid workdays at monthly gross / {month_workdays} workdays',
            dates=[date.isoformat() for date in sorted(unpaid_by_date)],
        )
    return salary


class PayrollManagementView(AdminRoleRequiredMixin, View):
    template_name = 'admin_dashboard/payroll.html'

    @staticmethod
    def period(request):
        today = timezone.localdate()
        try:
            month = int(request.GET.get('month', request.POST.get('month', today.month)))
            year = int(request.GET.get('year', request.POST.get('year', today.year)))
            if (
                not 1 <= month <= 12
                or not 2000 <= year <= today.year
                or (year, month) > (today.year, today.month)
            ):
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, 'Select a valid completed or current payroll month.')
            month, year = today.month, today.year
        month_start = datetime.date(year, month, 1)
        month_end = datetime.date(year, month, calendar.monthrange(year, month)[1])
        return month, year, month_start, month_end

    def get(self, request):
        month, year, month_start, month_end = self.period(request)
        salaries = Salary.objects.filter(
            month=month,
            year=year,
        ).exclude(status='cancelled').select_related('employee').prefetch_related('components').order_by(
            'employee__last_name',
            'employee__first_name',
        )
        rows = [get_salary_breakdown(salary) for salary in salaries]
        structures = SalaryStructure.objects.filter(is_active=True).select_related(
            'employee',
            'employee__department_record',
        ).order_by('employee__last_name', 'employee__first_name')
        context = {
            'rows': rows,
            'structures': structures,
            'selected_month': month,
            'selected_year': year,
            'months': [(number, calendar.month_name[number]) for number in range(1, 13)],
            'years': range(timezone.localdate().year - 3, timezone.localdate().year + 2),
            'pending_count': salaries.filter(status='pending').count(),
            'paid_count': salaries.filter(status='paid').count(),
            'structure_count': structures.count(),
        }
        return render(request, self.template_name, context)

    @transaction.atomic
    def post(self, request):
        action = request.POST.get('action')
        if action == 'process':
            month, year, month_start, month_end = self.period(request)
            holiday_dates = set(CompanyHoliday.objects.filter(
                date__range=(month_start, month_end),
            ).values_list('date', flat=True))
            created_count = 0
            missing_structure_count = 0
            employees = User.objects.filter(
                role='employee',
                is_active=True,
                employment_status__in=['active', 'on_leave'],
            ).select_related('salary_structure').prefetch_related(
                'salary_structure__revisions',
            )
            for employee in employees:
                if Salary.objects.filter(employee=employee, year=year, month=month).exists():
                    continue
                try:
                    structure = employee.salary_structure
                except SalaryStructure.DoesNotExist:
                    missing_structure_count += 1
                    continue
                if not structure.is_active:
                    missing_structure_count += 1
                    continue
                revision = next(
                    (
                        item for item in structure.revisions.all()
                        if item.effective_from <= month_end
                    ),
                    None,
                )
                if not revision:
                    missing_structure_count += 1
                    continue
                if _create_monthly_salary(
                    employee,
                    revision,
                    year,
                    month,
                    month_start,
                    month_end,
                    holiday_dates,
                ):
                    created_count += 1
            messages.success(
                request,
                f'Payroll prepared for {created_count} employee(s). '
                f'{missing_structure_count} active employee(s) had no applicable salary structure.',
            )
        elif action == 'mark_paid':
            salary = get_object_or_404(
                Salary,
                pk=request.POST.get('salary_id'),
                status__in=['pending', 'processing'],
            )
            salary.status = 'paid'
            salary.paid_date = timezone.localdate()
            salary.save(update_fields=['status', 'paid_date'])
            messages.success(request, 'Payroll marked as paid.')
        else:
            messages.error(request, 'Choose a valid payroll action.')
        month, year, _, _ = self.period(request)
        return redirect(f'{reverse("payroll_management")}?month={month}&year={year}')


class PayrollReportExportView(AdminRoleRequiredMixin, View):
    def get(self, request):
        month, year, _, _ = PayrollManagementView.period(request)
        salaries = Salary.objects.filter(
            month=month,
            year=year,
        ).exclude(status='cancelled').select_related('employee').prefetch_related('components').order_by(
            'employee__last_name',
            'employee__first_name',
        )
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="payroll-{year}-{month:02d}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Employee ID', 'Employee', 'Department', 'Month', 'Year', 'Gross', 'Deductions', 'Net Pay', 'Status', 'Paid Date'])
        for salary in salaries:
            breakdown = get_salary_breakdown(salary)
            writer.writerow([
                salary.employee.employee_id or '',
                salary.employee.get_full_name() or salary.employee.username,
                salary.employee.department or '',
                month,
                year,
                breakdown['gross'],
                breakdown['total_deductions'],
                breakdown['net_pay'],
                salary.get_status_display(),
                salary.paid_date or '',
            ])
        return response


class AdminPayslipDownloadView(AdminRoleRequiredMixin, View):
    def get(self, request, pk):
        salary = get_object_or_404(
            Salary.objects.select_related('employee').prefetch_related('components'),
            pk=pk,
            status='paid',
        )
        breakdown = get_salary_breakdown(salary)
        attendance_summary = get_salary_attendance_summary(
            salary,
            breakdown['deductions'],
        )
        return FileResponse(
            build_salary_payslip(salary, breakdown, attendance_summary),
            as_attachment=True,
            filename=f'payslip_{salary.employee.employee_id or salary.employee_id}_{salary.year}_{salary.month:02d}.pdf',
            content_type='application/pdf',
        )


class LeaveApprovalsView(AdminRoleRequiredMixin, View):
    """
    Lists pending leave requests and records the admin's decision and feedback.
    """
    template_name = 'admin_dashboard/leave_approvals.html'

    def get(self, request):
        pending_applications = list(LeaveApplication.objects.filter(status='pending').select_related(
            'employee', 'employee__manager', 'handover_contact'
        ).order_by('start_date', 'applied_on'))
        if pending_applications:
            earliest_date = min(application.start_date for application in pending_applications)
            latest_date = max(application.end_date for application in pending_applications)
            holiday_dates = set(CompanyHoliday.objects.filter(
                date__range=(earliest_date, latest_date),
            ).values_list('date', flat=True))
            for application in pending_applications:
                application.duration_days = get_leave_units(
                    application.start_date,
                    application.end_date,
                    application.half_day_session,
                    holiday_dates,
                )
        return render(request, self.template_name, {'pending_applications': pending_applications})

    @transaction.atomic
    def post(self, request):
        application = get_object_or_404(
            LeaveApplication.objects.select_for_update(),
            pk=request.POST.get('application_id'),
            status='pending',
        )
        action = request.POST.get('action')
        approval_notes = request.POST.get('approval_notes', '').strip()
        if action not in {'approve', 'reject'}:
            messages.error(request, 'Choose approve or reject for this leave request.')
        elif action == 'reject' and not approval_notes:
            messages.error(request, 'Add a reason when rejecting a leave request.')
        else:
            application.status = 'approved' if action == 'approve' else 'rejected'
            application.approved_by = request.user
            application.approval_notes = approval_notes
            application.save(update_fields=['status', 'approved_by', 'approval_notes'])
            transaction.on_commit(lambda: send_leave_status_email(application))
            messages.success(request, 'Leave request reviewed successfully.')
        return redirect('leave_approvals')


class ManagerOrAdminAttendanceMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.role != 'admin' and not request.user.direct_reports.filter(
            role='employee',
            is_active=True,
        ).exists():
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def team_queryset(self):
        employees = User.objects.filter(role='employee', is_active=True)
        if self.request.user.role != 'admin':
            employees = employees.filter(manager=self.request.user)
        return employees

    def selected_month(self):
        today = timezone.localdate()
        month_value = self.request.GET.get('month', str(today.month))
        year_value = self.request.GET.get('year', str(today.year))
        try:
            month, year = int(month_value), int(year_value)
            if not 1 <= month <= 12 or not 2000 <= year <= today.year + 3:
                raise ValueError
        except (TypeError, ValueError):
            messages.error(self.request, 'Select a valid reporting month and year.')
            month, year = today.month, today.year
        month_start = datetime.date(year, month, 1)
        month_end = datetime.date(year, month, calendar.monthrange(year, month)[1])
        return month, year, month_start, month_end


class AttendanceManagementView(ManagerOrAdminAttendanceMixin, View):
    template_name = 'admin_dashboard/attendance_management.html'

    def get(self, request):
        today = timezone.localdate()
        date_value = request.GET.get('date', today.isoformat())
        try:
            selected_date = datetime.date.fromisoformat(date_value)
        except (TypeError, ValueError):
            messages.error(request, 'Select a valid attendance date.')
            selected_date = today

        employees = list(self.team_queryset().select_related('manager').order_by('first_name', 'last_name', 'username'))
        employee_ids = [employee.pk for employee in employees]
        records_by_employee = {
            record.employee_id: record
            for record in Attendance.objects.filter(
                employee_id__in=employee_ids,
                date=selected_date,
            ).select_related('employee')
        }
        approved_leave_ids = set(LeaveApplication.objects.filter(
            employee_id__in=employee_ids,
            status='approved',
            start_date__lte=selected_date,
            end_date__gte=selected_date,
        ).values_list('employee_id', flat=True))
        holiday = CompanyHoliday.objects.filter(date=selected_date).first()
        is_past_workday = selected_date < today and selected_date.weekday() < 5 and not holiday
        daily_rows = []
        for employee in employees:
            attendance = records_by_employee.get(employee.pk)
            if attendance:
                status = attendance.get_status_display()
                missing_check_in = (
                    is_past_workday
                    and attendance.status in {'present', 'half_day'}
                    and not attendance.check_in
                )
                missing_check_out = (
                    is_past_workday
                    and attendance.status in {'present', 'half_day'}
                    and bool(attendance.check_in)
                    and not attendance.check_out
                )
            elif employee.pk in approved_leave_ids:
                status, missing_check_in, missing_check_out = 'On leave', False, False
            elif holiday:
                status, missing_check_in, missing_check_out = 'Holiday', False, False
            elif selected_date.weekday() >= 5:
                status, missing_check_in, missing_check_out = 'Weekend', False, False
            elif employee.joining_date and selected_date < employee.joining_date:
                status, missing_check_in, missing_check_out = 'Not employed', False, False
            elif selected_date < today:
                status, missing_check_in, missing_check_out = 'No attendance', True, False
            else:
                status, missing_check_in, missing_check_out = 'Not checked in', False, False
            daily_rows.append({
                'employee': employee,
                'attendance': attendance,
                'status': status,
                'missing_check_in': missing_check_in,
                'missing_check_out': missing_check_out,
            })

        month, year, month_start, month_end = self.selected_month()
        monthly_counts = {
            row['employee_id']: row
            for row in Attendance.objects.filter(
                employee_id__in=employee_ids,
                date__range=(month_start, month_end),
            ).values('employee_id').annotate(
                present=Count('id', filter=Q(status='present')),
                absent=Count('id', filter=Q(status='absent')),
                leave=Count('id', filter=Q(status='leave')),
                half_day=Count('id', filter=Q(status='half_day')),
                late=Count('id', filter=Q(check_in__gt=datetime.time(9, 15))),
            )
        }
        holiday_dates = set(CompanyHoliday.objects.filter(
            date__range=(month_start, min(month_end, today)),
        ).values_list('date', flat=True))
        missing_checkouts = {
            row['employee_id']: row['count']
            for row in Attendance.objects.filter(
                employee_id__in=employee_ids,
                date__range=(month_start, min(month_end, today - datetime.timedelta(days=1))),
                check_in__isnull=False,
                check_out__isnull=True,
                status__in=['present', 'half_day'],
            ).exclude(date__week_day__in=[1, 7]).exclude(
                date__in=holiday_dates
            ).values('employee_id').annotate(count=Count('id'))
        }
        monthly_rows = [
            {
                'employee': employee,
                **monthly_counts.get(employee.pk, {}),
                'missing_check_out': missing_checkouts.get(employee.pk, 0),
            }
            for employee in employees
        ]
        corrections = AttendanceCorrectionRequest.objects.filter(
            employee_id__in=employee_ids,
            status='pending',
        ).select_related('employee', 'employee__manager').order_by('date', 'created_at')
        return render(request, self.template_name, {
            'daily_rows': daily_rows,
            'selected_date': selected_date,
            'selected_month': month,
            'selected_year': year,
            'months': [(number, calendar.month_name[number]) for number in range(1, 13)],
            'years': range(today.year - 3, today.year + 4),
            'monthly_rows': monthly_rows,
            'pending_corrections': corrections,
            'pending_correction_count': corrections.count(),
            'holiday': holiday,
            'is_manager_view': request.user.role != 'admin',
        })

    @transaction.atomic
    def post(self, request):
        employee_scope = self.team_queryset()
        correction = get_object_or_404(
            AttendanceCorrectionRequest.objects.select_for_update(),
            pk=request.POST.get('correction_id'),
            employee__in=employee_scope,
            status='pending',
        )
        action = request.POST.get('action')
        notes = request.POST.get('approval_notes', '').strip()
        if action not in {'approve', 'reject'}:
            messages.error(request, 'Choose approve or reject for this correction request.')
        elif action == 'reject' and not notes:
            messages.error(request, 'Add a reason when rejecting an attendance correction.')
        else:
            if action == 'approve':
                attendance, _ = Attendance.objects.get_or_create(
                    employee=correction.employee,
                    date=correction.date,
                    defaults={'status': 'present'},
                )
                if correction.requested_check_in:
                    attendance.check_in = correction.requested_check_in
                if correction.requested_check_out:
                    attendance.check_out = correction.requested_check_out
                attendance.status = 'present'
                attendance.save(update_fields=['check_in', 'check_out', 'status'])
            correction.status = 'approved' if action == 'approve' else 'rejected'
            correction.approval_notes = notes
            correction.reviewed_by = request.user
            correction.reviewed_at = timezone.now()
            correction.save(update_fields=[
                'status',
                'approval_notes',
                'reviewed_by',
                'reviewed_at',
            ])
            messages.success(request, 'Attendance correction reviewed successfully.')
        return redirect('attendance_management')


class AttendanceReportExportView(ManagerOrAdminAttendanceMixin, View):
    def get(self, request):
        month, year, month_start, month_end = self.selected_month()
        employee_ids = self.team_queryset().values_list('pk', flat=True)
        records = Attendance.objects.filter(
            employee_id__in=employee_ids,
            date__range=(month_start, month_end),
        ).select_related('employee').order_by('date', 'employee__last_name', 'employee__first_name')
        holiday_dates = set(CompanyHoliday.objects.filter(
            date__range=(month_start, month_end),
        ).values_list('date', flat=True))
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="attendance-{year}-{month:02d}.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Employee ID',
            'Employee',
            'Department',
            'Date',
            'Status',
            'Check in',
            'Check out',
            'Missing check-in',
            'Missing check-out',
            'Location mode',
            'Remarks',
        ])
        today = timezone.localdate()
        for record in records:
            past_workday = (
                record.date < today
                and record.date.weekday() < 5
                and record.date not in holiday_dates
            )
            writer.writerow([
                record.employee.employee_id or '',
                record.employee.get_full_name() or record.employee.username,
                record.employee.department or '',
                record.date.isoformat(),
                record.get_status_display(),
                record.check_in or '',
                record.check_out or '',
                bool(
                    past_workday
                    and record.status in {'present', 'half_day'}
                    and not record.check_in
                ),
                bool(
                    past_workday
                    and record.status in {'present', 'half_day'}
                    and record.check_in
                    and not record.check_out
                ),
                record.get_location_mode_display() or '',
                record.remarks,
            ])
        return response


class LeavePolicyConfigurationView(AdminRoleRequiredMixin, View):
    template_name = 'admin_dashboard/leave_policies.html'
    DOCUMENT_REQUIRED_DEFAULTS = {'Sick', 'Maternity', 'Paternity'}

    def get_policies(self):
        policies = []
        for leave_type, label in LeaveApplication.LEAVE_TYPE_CHOICES:
            policy, _ = LeavePolicy.objects.get_or_create(
                leave_type=leave_type,
                defaults={
                    'is_paid': leave_type != 'Unpaid',
                    'requires_document': leave_type in self.DOCUMENT_REQUIRED_DEFAULTS,
                },
            )
            policies.append((policy, label))
        return policies

    def get(self, request):
        return render(request, self.template_name, {
            'policy_rows': [
                (policy, label, LeavePolicyForm(instance=policy))
                for policy, label in self.get_policies()
            ],
        })

    def post(self, request):
        policy = get_object_or_404(LeavePolicy, pk=request.POST.get('policy_id'))
        form = LeavePolicyForm(request.POST, instance=policy)
        if form.is_valid():
            form.save()
            messages.success(request, f'{policy.get_leave_type_display()} policy updated.')
        else:
            messages.error(request, 'Correct the policy fields and try again.')
        return redirect('leave_policies')


class AdminLeaveCalendarView(AdminRoleRequiredMixin, View):
    template_name = 'admin_dashboard/leave_calendar.html'

    def get(self, request):
        today = timezone.localdate()
        try:
            month = int(request.GET.get('month', today.month))
            year = int(request.GET.get('year', today.year))
            if not 1 <= month <= 12 or not 2000 <= year <= today.year + 3:
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, 'Select a valid calendar month and year.')
            month, year = today.month, today.year

        month_start = datetime.date(year, month, 1)
        month_end = datetime.date(year, month, calendar.monthrange(year, month)[1])
        events_by_date = {}
        for holiday in CompanyHoliday.objects.filter(
            date__range=(month_start, month_end),
        ):
            events_by_date.setdefault(holiday.date, []).append({
                'kind': 'holiday',
                'title': holiday.name,
            })

        approved_leaves = LeaveApplication.objects.filter(
            status='approved',
            start_date__lte=month_end,
            end_date__gte=month_start,
            employee__role='employee',
            employee__is_active=True,
        ).select_related('employee').order_by('employee__last_name', 'employee__first_name')
        for leave in approved_leaves:
            current_date = max(leave.start_date, month_start)
            last_date = min(leave.end_date, month_end)
            while current_date <= last_date:
                if current_date.weekday() < 5:
                    events_by_date.setdefault(current_date, []).append({
                        'kind': 'leave',
                        'title': f'{leave.employee.get_full_name() or leave.employee.username} · {leave.get_leave_type_display()}',
                    })
                current_date += datetime.timedelta(days=1)

        weeks = []
        for week in calendar.Calendar(firstweekday=6).monthdatescalendar(year, month):
            weeks.append([
                {
                    'date': day,
                    'is_current_month': day.month == month,
                    'is_today': day == today,
                    'events': events_by_date.get(day, []),
                }
                for day in week
            ])
        if month == 1:
            prev_month, prev_year = 12, year - 1
        else:
            prev_month, prev_year = month - 1, year
        if month == 12:
            next_month, next_year = 1, year + 1
        else:
            next_month, next_year = month + 1, year
        return render(request, self.template_name, {
            'weeks': weeks,
            'weekday_labels': ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
            'month_name': calendar.month_name[month],
            'selected_month': month,
            'selected_year': year,
            'prev_month': prev_month,
            'prev_year': prev_year,
            'next_month': next_month,
            'next_year': next_year,
            'months': [(number, calendar.month_name[number]) for number in range(1, 13)],
            'years': range(today.year - 3, today.year + 4),
        })


class AdminLeaveDocumentView(AdminRoleRequiredMixin, View):
    def get(self, request, pk):
        application = get_object_or_404(LeaveApplication, pk=pk)
        if not application.supporting_document:
            raise Http404
        return FileResponse(
            application.supporting_document.open('rb'),
            as_attachment=True,
            filename=Path(application.supporting_document.name).name,
            content_type='application/octet-stream',
        )


class AdminLoginView(LoginView):
    """
    Sign in and route the user through the role-aware portal redirect.
    """
    template_name = 'admin_dashboard/login.html'
    redirect_authenticated_user = False

    def dispatch(self, request, *args, **kwargs):
        self.expected_role = kwargs.pop('expected_role', 'admin')
        self.login_url_name = 'admin_login' if self.expected_role == 'admin' else 'employee_login'
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if getattr(form.get_user(), 'role', None) != self.expected_role:
            messages.error(self.request, 'This account belongs to a different portal. Use the matching sign-in page.')
            return redirect(self.login_url_name)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('admin_dashboard' if self.expected_role == 'admin' else 'employee_dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['portal_title'] = 'HRMS Admin Portal' if self.expected_role == 'admin' else 'HRMS Employee Portal'
        return context


class AdminLogoutView(View):
    """
    Simple View to log out and redirect to login page.
    """
    def get(self, request, portal='employee'):
        logout(request)
        return redirect('admin_login' if portal == 'admin' else 'employee_login')
