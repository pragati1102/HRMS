from rest_framework.permissions import BasePermission
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied

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
            # Return 403 Forbidden
            raise PermissionDenied("You do not have permission to access this dashboard.")
        # Otherwise redirect to login page
        return super().handle_no_permission()


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
            raise PermissionDenied("Only employees can access this portal.")
        return super().handle_no_permission()
