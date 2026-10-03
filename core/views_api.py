from rest_framework.generics import ListAPIView
from django.db.models import Q
from .models import User
from .serializers import EmployeeListSerializer
from .permissions import IsAdminRole

class EmployeeListAPIView(ListAPIView):
    """
    API endpoint that lists all employees. Accessible only by admin users.
    Supports search by name and filters by department and role.
    """
    serializer_class = EmployeeListSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        # Prefetch today's attendance to avoid N+1 query problem
        queryset = User.objects.all().order_by('username').prefetch_related('attendances')
        
        # Search by name (checks first_name, last_name, and username)
        search_query = self.request.query_params.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(personal_email__icontains=search_query) |
                Q(employee_id__icontains=search_query)
            )
            
        # Filter by department
        department = self.request.query_params.get('department', '').strip()
        if department:
            queryset = queryset.filter(department__iexact=department)
            
        # Filter by role
        role = self.request.query_params.get('role', '').strip()
        if role:
            queryset = queryset.filter(role=role)

        employment_status = self.request.query_params.get('employment_status', '').strip()
        if employment_status in dict(User.EMPLOYMENT_STATUS_CHOICES):
            queryset = queryset.filter(employment_status=employment_status)
            
        return queryset
