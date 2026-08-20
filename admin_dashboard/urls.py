from django.urls import path
from .views import (
    RootRedirectView,
    EmployeeListView,
    EmployeeDetailView,
    LeaveApprovalsView,
    AdminLoginView,
    AdminLogoutView,
)

urlpatterns = [
    path('', RootRedirectView.as_view(), name='root_redirect'),
    path('admin/employees/', EmployeeListView.as_view(), name='employee_list'),
    path('admin/employees/<int:pk>/', EmployeeDetailView.as_view(), name='employee_detail'),
    path('admin/leaves/', LeaveApprovalsView.as_view(), name='leave_approvals'),
    path('login/', AdminLoginView.as_view(), name='admin_login'),
    path('logout/', AdminLogoutView.as_view(), name='admin_logout'),
]
