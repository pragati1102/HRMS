import datetime
from django.views.generic import ListView, DetailView, TemplateView
from django.db.models import Q, Count
from django.contrib.auth.views import LoginView
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.views import View
from django.utils import timezone
from core.models import User, Attendance, WorkLog, LeaveApplication, Salary
from core.permissions import AdminRoleRequiredMixin

class RootRedirectView(View):
    """
    Redirects user on login to their appropriate portal (Admin vs Employee).
    """
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('admin_login')
        if getattr(request.user, 'role', None) == 'admin':
            return redirect('employee_list')
        else:
            return redirect('employee_dashboard')


class EmployeeListView(AdminRoleRequiredMixin, ListView):
    """
    Dashboard view that lists all employees with searching and filtering.
    Restricted to admin users.
    """
    model = User
    template_name = 'admin_dashboard/employee_list.html'
    context_object_name = 'employees'

    def get_queryset(self):
        queryset = User.objects.all().order_by('username').prefetch_related('attendances')
        
        # Apply search by name
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(username__icontains=search_query)
            )
            
        # Apply department filter
        department = self.request.GET.get('department', '').strip()
        if department:
            queryset = queryset.filter(department__iexact=department)
            
        # Apply role filter
        role = self.request.GET.get('role', '').strip()
        if role:
            queryset = queryset.filter(role=role)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = (
            User.objects.exclude(department__isnull=True)
            .exclude(department='')
            .values_list('department', flat=True)
            .distinct()
        )
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_department'] = self.request.GET.get('department', '')
        context['selected_role'] = self.request.GET.get('role', '')
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
        })
        return context


class LeaveApprovalsView(AdminRoleRequiredMixin, TemplateView):
    """
    Page listing all pending leaves for approval (Admin only).
    """
    template_name = 'admin_dashboard/leave_approvals.html'


class AdminLoginView(LoginView):
    """
    Standard Login View using Django auth.
    """
    template_name = 'admin_dashboard/login.html'
    
    def get_success_url(self):
        # Redirect to employee list dashboard
        return '/'


class AdminLogoutView(View):
    """
    Simple View to log out and redirect to login page.
    """
    def get(self, request):
        logout(request)
        return redirect('admin_login')
