from django.urls import path
from .views import (
    RootRedirectView,
    EmployeeListView,
    EmployeeDetailView,
    LeaveApprovalsView,
    AdminLeaveDocumentView,
    AdminLoginView,
    AdminLogoutView,
)

urlpatterns = [
    path('', RootRedirectView.as_view(), name='root_redirect'),
    path('admin/employees/', EmployeeListView.as_view(), name='employee_list'),
    path('admin/employees/<int:pk>/', EmployeeDetailView.as_view(), name='employee_detail'),
    path('hr/leaves/', LeaveApprovalsView.as_view(), name='leave_approvals'),
    path('hr/leaves/<int:pk>/document/', AdminLeaveDocumentView.as_view(), name='admin_leave_document'),
    path('login/', AdminLoginView.as_view(), name='admin_login'),
    path('logout/', AdminLogoutView.as_view(), name='admin_logout'),
]
