from django.urls import path
from .views_api import EmployeeListAPIView
from .views import (
    EmployeeDashboardView,
    EmployeeCheckInView,
    EmployeeCheckOutView,
    EmployeeAttendanceView,
    EmployeeWorkLogsView,
    EmployeeAddWorkLogView,
    EmployeeDeleteWorkLogView,
    EmployeeEditWorkLogView,
    EmployeeLeavesView,
    EmployeeApplyLeaveView,
    EmployeeProfileView,
    EmployeeSalaryView,
    EmployeeCalendarView,
    EmployeeProjectsView,
)

urlpatterns = [
    # APIs
    path('employees/', EmployeeListAPIView.as_view(), name='api_employee_list'),
    
    # Employee Views
    path('dashboard/', EmployeeDashboardView.as_view(), name='employee_dashboard'),
    path('check-in/', EmployeeCheckInView.as_view(), name='employee_check_in'),
    path('check-out/', EmployeeCheckOutView.as_view(), name='employee_check_out'),
    path('attendance/', EmployeeAttendanceView.as_view(), name='employee_attendance'),
    path('work-logs/', EmployeeWorkLogsView.as_view(), name='employee_work_logs'),
    path('work-logs/add/', EmployeeAddWorkLogView.as_view(), name='employee_add_worklog'),
    path('work-logs/delete/<int:pk>/', EmployeeDeleteWorkLogView.as_view(), name='employee_delete_worklog'),
    path('work-logs/edit/<int:pk>/', EmployeeEditWorkLogView.as_view(), name='employee_edit_worklog'),
    path('leaves/', EmployeeLeavesView.as_view(), name='employee_leaves'),
    path('leaves/apply/', EmployeeApplyLeaveView.as_view(), name='employee_apply_leave'),
    path('profile/', EmployeeProfileView.as_view(), name='employee_profile'),
    path('salary/', EmployeeSalaryView.as_view(), name='employee_salary'),
    path('calendar/', EmployeeCalendarView.as_view(), name='employee_calendar'),
    path('projects/', EmployeeProjectsView.as_view(), name='employee_projects'),
]

