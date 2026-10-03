from rest_framework.permissions import BasePermission
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.shortcuts import redirect

class IsAdminRole(BasePermission):
    """
    Allows access only to users who have role == 'admin'.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and getattr(request.user, 'role', None) == 'admin')


class AdminRoleRequiredMixin(UserPassesTestMixin):
    """
    Standard Django Class-Based View Mixin to restrict access to Admins only.
    Raises 403 PermissionDenied for logged-in non-admins.
    Redirects to login for unauthenticated users.
    """
    def test_func(self):
        return (
            self.request.user.is_authenticated 
            and getattr(self.request.user, 'role', None) == 'admin'
        )

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            if getattr(self.request.user, 'role', None) == 'employee':
                return redirect('employee_dashboard')
            return render(self.request, 'admin_dashboard/access_denied.html', status=403)
        # Otherwise redirect to login page
        return redirect('admin_login')


class EmployeeRoleRequiredMixin(UserPassesTestMixin):
    """
    Standard Django Class-Based View Mixin to restrict access to Employees only.
    Raises 403 PermissionDenied for logged-in non-employees.
    Redirects to login for unauthenticated users.
    """
    def test_func(self):
        return (
            self.request.user.is_authenticated 
            and getattr(self.request.user, 'role', None) == 'employee'
        )

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            if getattr(self.request.user, 'role', None) == 'admin':
                return redirect('admin_dashboard')
            raise PermissionDenied("Only employees can access this portal.")
        return redirect('employee_login')
