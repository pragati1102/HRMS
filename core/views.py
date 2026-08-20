import datetime
import calendar
from django.views.generic import TemplateView
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from .models import User, Attendance, WorkLog, LeaveApplication, Salary, Project
from .permissions import EmployeeRoleRequiredMixin

def get_leave_days_in_range(employee, start_limit, end_limit):
    """
    Calculates the total days of approved leave in the specified range.
    """
    leaves = LeaveApplication.objects.filter(
        employee=employee,
        status='approved',
        start_date__lte=end_limit,
        end_date__gte=start_limit
    )
    total_days = 0
    for leave in leaves:
        overlap_start = max(leave.start_date, start_limit)
        overlap_end = min(leave.end_date, end_limit)
        if overlap_start <= overlap_end:
            total_days += (overlap_end - overlap_start).days + 1
    return total_days


class EmployeeDashboardView(EmployeeRoleRequiredMixin, TemplateView):
    """
    Dashboard for the logged-in employee. Shows module quick links and
    a feed of recent work log activity.
    """
    template_name = 'core/employee_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        pending_applications_count = LeaveApplication.objects.filter(employee=user, status='pending').count()
        recent_activity = WorkLog.objects.filter(employee=user).order_by('-date', '-start_time')[:5]

        context.update({
            'pending_applications_count': pending_applications_count,
            'recent_activity': recent_activity,
        })
        return context


class EmployeeCheckInView(EmployeeRoleRequiredMixin, View):
    """
    Marks today's attendance as present and logs check-in time.
    """
    def post(self, request):
        today = timezone.localdate()
        att = Attendance.objects.filter(employee=request.user, date=today).first()
        if att and att.check_in:
            messages.warning(request, "You have already checked in today.")
            return redirect(request.META.get('HTTP_REFERER', 'employee_attendance'))
            
        att, created = Attendance.objects.get_or_create(
            employee=request.user, 
            date=today,
            defaults={
                'status': 'present',
                'check_in': timezone.localtime().time()
            }
        )
        if not created:
            if att.status in ['absent', 'leave', 'no_record']:
                att.status = 'present'
            if not att.check_in:
                att.check_in = timezone.localtime().time()
            att.save()
            messages.info(request, "Today's check-in has been logged.")
        else:
            messages.success(request, "Checked in successfully!")
        return redirect(request.META.get('HTTP_REFERER', 'employee_attendance'))


class EmployeeCheckOutView(EmployeeRoleRequiredMixin, View):
    """
    Logs check-out time for today's attendance.
    """
    def post(self, request):
        today = timezone.localdate()
        att = Attendance.objects.filter(employee=request.user, date=today).first()
        if att:
            if att.check_out:
                messages.warning(request, "You have already checked out today.")
            else:
                att.check_out = timezone.localtime().time()
                att.save()
                messages.success(request, "Checked out successfully!")
        else:
            messages.error(request, "No attendance record found for today. Please check-in first.")
        return redirect(request.META.get('HTTP_REFERER', 'employee_attendance'))


class EmployeeAttendanceView(EmployeeRoleRequiredMixin, TemplateView):
    """
    Shows today's attendance marking options, monthly summary stats,
    and history table filterable by month/year.
    """
    template_name = 'core/attendance.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()
        
        # Month/Year Filter (default to current month/year)
        month_str = self.request.GET.get('month')
        year_str = self.request.GET.get('year')
        
        selected_month = int(month_str) if month_str and month_str.isdigit() else today.month
        selected_year = int(year_str) if year_str and year_str.isdigit() else today.year
        
        # Filtered history records
        attendances = Attendance.objects.filter(
            employee=user, 
            date__month=selected_month, 
            date__year=selected_year
        ).order_by('-date')
        
        # Monthly statistics based on filtered month
        total_present = attendances.filter(status='present').count()
        total_absent = attendances.filter(status='absent').count()
        total_half_days = attendances.filter(status='half_day').count()
        
        # Generate filter selections
        months = [(i, calendar.month_name[i]) for i in range(1, 13)]
        years = range(today.year - 3, today.year + 3)
        
        # Today's attendance record
        today_attendance = Attendance.objects.filter(employee=user, date=today).first()
        
        context.update({
            'attendances': attendances,
            'selected_month': selected_month,
            'selected_year': selected_year,
            'total_present': total_present,
            'total_absent': total_absent,
            'total_half_days': total_half_days,
            'months': months,
            'years': years,
            'today_attendance': today_attendance,
            'today': today,
        })
        return context


class EmployeeWorkLogsView(EmployeeRoleRequiredMixin, TemplateView):
    """
    Manages daily work logging: form to add slots, today's log listing with edit/delete,
    and history list filterable by date range grouped by day.
    """
    template_name = 'core/work_logs.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()
        
        # Today's logs
        today_work_logs = WorkLog.objects.filter(employee=user, date=today).order_by('start_time')
        total_hours_today = sum(log.hours_worked for log in today_work_logs) if today_work_logs else 0
        
        # Date range filters
        start_date_str = self.request.GET.get('start_date', '')
        end_date_str = self.request.GET.get('end_date', '')
        
        history_logs = WorkLog.objects.filter(employee=user).order_by('-date', '-start_time')
        
        if start_date_str:
            try:
                start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                history_logs = history_logs.filter(date__gte=start_date)
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
                history_logs = history_logs.filter(date__lte=end_date)
            except ValueError:
                pass
                
        # Group history in Python
        logs_by_day = {}
        for log in history_logs:
            logs_by_day.setdefault(log.date, []).append(log)
            
        grouped_history = []
        for date in sorted(logs_by_day.keys(), reverse=True):
            day_logs = logs_by_day[date]
            total_hours = sum(l.hours_worked for l in day_logs)
            grouped_history.append({
                'date': date,
                'logs': day_logs,
                'total_hours': total_hours
            })
            
        context.update({
            'today_work_logs': today_work_logs,
            'total_hours_today': total_hours_today,
            'grouped_history': grouped_history,
            'start_date': start_date_str,
            'end_date': end_date_str,
            'today': today,
            'categories': ['Meeting', 'Development', 'Bug Fix', 'Documentation', 'Testing', 'Other'],
        })
        return context


class EmployeeAddWorkLogView(EmployeeRoleRequiredMixin, View):
    """
    Adds a new work log entry. Validates date, range, and slot overlaps.
    """
    def post(self, request):
        date_str = request.POST.get('date')
        start_time_str = request.POST.get('start_time')
        end_time_str = request.POST.get('end_time')
        description = request.POST.get('description', '').strip()
        category = request.POST.get('category', 'Other')
        
        if not start_time_str or not end_time_str or not description:
            messages.error(request, "Start time, end time, and description are required.")
            return redirect('employee_work_logs')
            
        try:
            if date_str:
                log_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                log_date = timezone.localdate()
                
            start_time = datetime.datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.datetime.strptime(end_time_str, '%H:%M').time()
            
            if start_time >= end_time:
                messages.error(request, "End time must be after start time.")
                return redirect('employee_work_logs')
                
            # Overlap check
            overlap = WorkLog.objects.filter(
                employee=request.user,
                date=log_date,
                start_time__lt=end_time,
                end_time__gt=start_time
            ).exists()
            
            if overlap:
                messages.error(request, "Error: This slot overlaps with another work log entry for the same day.")
                return redirect('employee_work_logs')
                
            WorkLog.objects.create(
                employee=request.user,
                date=log_date,
                start_time=start_time,
                end_time=end_time,
                description=description,
                category=category
            )
            messages.success(request, "Work log entry added successfully!")
        except Exception as e:
            messages.error(request, f"Error saving work log: {str(e)}")
            
        return redirect('employee_work_logs')


class EmployeeDeleteWorkLogView(EmployeeRoleRequiredMixin, View):
    """
    Deletes a work log entry only if it belongs to the current day.
    """
    def post(self, request, pk):
        log = get_object_or_404(WorkLog, pk=pk, employee=request.user)
        today = timezone.localdate()
        if log.date != today:
            messages.error(request, "You can only delete work log entries created today.")
        else:
            log.delete()
            messages.success(request, "Work log entry deleted successfully.")
        return redirect('employee_work_logs')


class EmployeeEditWorkLogView(EmployeeRoleRequiredMixin, View):
    """
    Renders edit page and handles edit submission. Restricted to current day logs.
    """
    template_name = 'core/edit_work_log.html'

    def get(self, request, pk):
        log = get_object_or_404(WorkLog, pk=pk, employee=request.user)
        today = timezone.localdate()
        if log.date != today:
            messages.error(request, "You can only edit work log entries created today.")
            return redirect('employee_work_logs')
        
        categories = ['Meeting', 'Development', 'Bug Fix', 'Documentation', 'Testing', 'Other']
        return render(request, self.template_name, {'log': log, 'categories': categories})

    def post(self, request, pk):
        log = get_object_or_404(WorkLog, pk=pk, employee=request.user)
        today = timezone.localdate()
        if log.date != today:
            messages.error(request, "You can only edit work log entries created today.")
            return redirect('employee_work_logs')
            
        start_time_str = request.POST.get('start_time')
        end_time_str = request.POST.get('end_time')
        description = request.POST.get('description', '').strip()
        category = request.POST.get('category', 'Other')
        
        if not start_time_str or not end_time_str or not description:
            messages.error(request, "All fields are required.")
            return redirect('employee_edit_worklog', pk=pk)
            
        try:
            start_time = datetime.datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.datetime.strptime(end_time_str, '%H:%M').time()
            
            if start_time >= end_time:
                messages.error(request, "End time must be after start time.")
                return redirect('employee_edit_worklog', pk=pk)
                
            overlap = WorkLog.objects.filter(
                employee=request.user,
                date=log.date,
                start_time__lt=end_time,
                end_time__gt=start_time
            ).exclude(id=log.id).exists()
            
            if overlap:
                messages.error(request, "Error: This slot overlaps with another work log entry.")
                return redirect('employee_edit_worklog', pk=pk)
                
            log.start_time = start_time
            log.end_time = end_time
            log.description = description
            log.category = category
            log.save()
            
            messages.success(request, "Work log updated successfully!")
            return redirect('employee_work_logs')
        except Exception as e:
            messages.error(request, f"Error saving work log: {str(e)}")
            return redirect('employee_edit_worklog', pk=pk)


class EmployeeLeavesView(EmployeeRoleRequiredMixin, TemplateView):
    """
    Renders the leave application form and list of personal applications.
    """
    template_name = 'core/leaves.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()
        
        # Statistics (Annual total leaves, pending applications)
        first_day_of_year = datetime.date(today.year, 1, 1)
        last_day_of_year = datetime.date(today.year, 12, 31)
        leaves_taken_year = get_leave_days_in_range(user, first_day_of_year, last_day_of_year)
        pending_applications_count = LeaveApplication.objects.filter(employee=user, status='pending').count()
        
        # Applications list
        leave_applications = LeaveApplication.objects.filter(employee=user).order_by('-applied_on')
        
        context.update({
            'leaves_taken_year': leaves_taken_year,
            'pending_applications_count': pending_applications_count,
            'leave_applications': leave_applications,
            'today': today,
            'leave_types': ['Sick', 'Casual', 'Paid'],
        })
        return context


class EmployeeApplyLeaveView(EmployeeRoleRequiredMixin, View):
    """
    Handles submission of new leave applications. Validates start and end dates.
    """
    def post(self, request):
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        reason = request.POST.get('reason', '').strip()
        leave_type = request.POST.get('leave_type', 'Casual')
        
        if not start_date_str or not end_date_str or not reason:
            messages.error(request, "All fields (start date, end date, reason) are required.")
            return redirect('employee_leaves')
            
        try:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            today = timezone.localdate()
            
            if start_date < today:
                messages.error(request, "Leave start date cannot be in the past.")
                return redirect('employee_leaves')
                
            if start_date > end_date:
                messages.error(request, "End date cannot be before start date.")
                return redirect('employee_leaves')
                
            LeaveApplication.objects.create(
                employee=request.user,
                start_date=start_date,
                end_date=end_date,
                reason=reason,
                leave_type=leave_type,
                status='pending'
            )
            messages.success(request, "Leave application submitted successfully!")
        except Exception as e:
            messages.error(request, f"Error submitting leave application: {str(e)}")
            
        return redirect('employee_leaves')


class EmployeeProfileView(EmployeeRoleRequiredMixin, View):
    """
    Renders personal profile details and allows updating phone number and address.
    """
    template_name = 'core/profile.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        user = request.user
        phone_number = request.POST.get('phone_number', '').strip()
        address = request.POST.get('address', '').strip()
        
        if not phone_number:
            messages.error(request, "Phone number is required.")
            return render(request, self.template_name)
            
        user.phone_number = phone_number
        user.address = address
        user.save()
        
        messages.success(request, "Profile updated successfully!")
        return redirect('employee_profile')


class EmployeeSalaryView(EmployeeRoleRequiredMixin, TemplateView):
    """
    Displays current month's salary details and payment history.
    """
    template_name = 'core/salary.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()
        
        # Current month salary record
        current_salary = Salary.objects.filter(
            employee=user,
            month=today.month,
            year=today.year
        ).first()
        
        if current_salary:
            current_status = current_salary.status.title()
            current_amount = current_salary.amount
        else:
            current_status = "Pending"
            current_amount = user.salary_amount
            
        # Next salary due date
        next_salary_date = user.get_next_salary_due_date()
        
        # Salary history table
        salary_history = Salary.objects.filter(employee=user).order_by('-year', '-month')
        
        context.update({
            'current_status': current_status,
            'current_amount': current_amount,
            'next_salary_date': next_salary_date,
            'salary_history': salary_history,
        })
        return context


class EmployeeCalendarView(EmployeeRoleRequiredMixin, TemplateView):
    """
    Month-grid calendar combining the employee's own attendance status
    and leave applications (approved/pending) for the selected month.
    """
    template_name = 'core/calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()

        month_str = self.request.GET.get('month')
        year_str = self.request.GET.get('year')
        selected_month = int(month_str) if month_str and month_str.isdigit() else today.month
        selected_year = int(year_str) if year_str and year_str.isdigit() else today.year

        month_start = datetime.date(selected_year, selected_month, 1)
        month_end = datetime.date(selected_year, selected_month, calendar.monthrange(selected_year, selected_month)[1])

        attendance_map = {
            att.date.day: att.status
            for att in Attendance.objects.filter(employee=user, date__year=selected_year, date__month=selected_month)
        }

        leave_map = {}
        leaves = LeaveApplication.objects.filter(
            employee=user,
            start_date__lte=month_end,
            end_date__gte=month_start,
        ).order_by('status')
        for leave in leaves:
            day = max(leave.start_date, month_start)
            end = min(leave.end_date, month_end)
            while day <= end:
                if day.day not in leave_map or leave.status == 'approved':
                    leave_map[day.day] = leave.status
                day += datetime.timedelta(days=1)

        cal = calendar.Calendar(firstweekday=6)  # Sunday-first
        weeks = []
        for week in cal.monthdayscalendar(selected_year, selected_month):
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append(None)
                else:
                    day_date = datetime.date(selected_year, selected_month, day)
                    week_data.append({
                        'day': day,
                        'is_today': day_date == today,
                        'is_weekend': day_date.weekday() >= 5,
                        'attendance_status': attendance_map.get(day),
                        'leave_status': leave_map.get(day),
                    })
            weeks.append(week_data)

        if selected_month == 1:
            prev_month, prev_year = 12, selected_year - 1
        else:
            prev_month, prev_year = selected_month - 1, selected_year
        if selected_month == 12:
            next_month, next_year = 1, selected_year + 1
        else:
            next_month, next_year = selected_month + 1, selected_year

        context.update({
            'weeks': weeks,
            'selected_month': selected_month,
            'selected_year': selected_year,
            'month_name': calendar.month_name[selected_month],
            'prev_month': prev_month,
            'prev_year': prev_year,
            'next_month': next_month,
            'next_year': next_year,
            'today': today,
        })
        return context


class EmployeeProjectsView(EmployeeRoleRequiredMixin, TemplateView):
    """
    Lists the projects the logged-in employee is currently working on.
    """
    template_name = 'core/projects.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        projects = user.projects.all().order_by('-status', 'name')
        context.update({
            'active_projects': [p for p in projects if p.status == 'active'],
            'other_projects': [p for p in projects if p.status != 'active'],
        })
        return context

