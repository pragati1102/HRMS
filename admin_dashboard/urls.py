from django.urls import path
from .views import (
    RootRedirectView,
    AdminDashboardView,
    EmployeeListView,
    EmployeeCreateView,
    EmployeeUpdateView,
    EmployeeDeactivateView,
    EmployeeActivateView,
    EmployeeDocumentUploadView,
    EmployeeDocumentDownloadView,
    EmployeeDocumentDeleteView,
    EmployeeDetailView,
    LeaveApprovalsView,
    AttendanceManagementView,
    AttendanceReportExportView,
    LeavePolicyConfigurationView,
    AdminLeaveCalendarView,
    DepartmentManagementView,
    SalaryStructureManagementView,
    PayrollManagementView,
    PayrollReportExportView,
    AdminPayslipDownloadView,
    AdminLeaveDocumentView,
    AdminLoginView,
    AdminLogoutView,
)

urlpatterns = [
    path('', RootRedirectView.as_view(), name='root_redirect'),

    # Unified login page for both admin and employee. Keep named aliases for
    # compatibility with existing code/tests while using the same view/URL.
    path('login/', AdminLoginView.as_view(), name='login'),
    path('hr/login/', AdminLoginView.as_view(), name='admin_login'),
    path('employee/login/', AdminLoginView.as_view(), name='employee_login'),

    path('hr/dashboard/', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('hr/organization/', DepartmentManagementView.as_view(), name='organization_management'),
    path('hr/payroll/', PayrollManagementView.as_view(), name='payroll_management'),
    path('hr/payroll/report/', PayrollReportExportView.as_view(), name='payroll_report_export'),
    path('hr/payroll/structures/add/', SalaryStructureManagementView.as_view(), name='salary_structure_create'),
    path('hr/payroll/structures/<int:pk>/edit/', SalaryStructureManagementView.as_view(), name='salary_structure_edit'),
    path('hr/payroll/payslips/<int:pk>/', AdminPayslipDownloadView.as_view(), name='admin_payslip_download'),
    path('hr/employees/', EmployeeListView.as_view(), name='employee_list'),
    path('hr/employees/add/', EmployeeCreateView.as_view(), name='employee_create'),
    path('hr/employees/<int:pk>/', EmployeeDetailView.as_view(), name='employee_detail'),
    path('hr/employees/<int:pk>/edit/', EmployeeUpdateView.as_view(), name='employee_edit'),
    path('hr/employees/<int:pk>/deactivate/', EmployeeDeactivateView.as_view(), name='employee_deactivate'),
    path('hr/employees/<int:pk>/activate/', EmployeeActivateView.as_view(), name='employee_activate'),
    path('hr/employees/<int:pk>/documents/upload/', EmployeeDocumentUploadView.as_view(), name='employee_document_upload'),
    path('hr/employees/<int:pk>/documents/<int:document_pk>/download/', EmployeeDocumentDownloadView.as_view(), name='employee_document_download'),
    path('hr/employees/<int:pk>/documents/<int:document_pk>/delete/', EmployeeDocumentDeleteView.as_view(), name='employee_document_delete'),
    path('hr/leaves/', LeaveApprovalsView.as_view(), name='leave_approvals'),
    path('hr/leaves/policies/', LeavePolicyConfigurationView.as_view(), name='leave_policies'),
    path('hr/leaves/calendar/', AdminLeaveCalendarView.as_view(), name='admin_leave_calendar'),
    path('hr/attendance/', AttendanceManagementView.as_view(), name='attendance_management'),
    path('hr/attendance/export/', AttendanceReportExportView.as_view(), name='attendance_report_export'),
    path('hr/leaves/<int:pk>/document/', AdminLeaveDocumentView.as_view(), name='admin_leave_document'),

    # Unified logout that returns to the single login page
    path('hr/logout/', AdminLogoutView.as_view(), name='admin_logout'),
    path('employee/logout/', AdminLogoutView.as_view(), name='employee_logout'),
]
