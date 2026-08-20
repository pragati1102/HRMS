from rest_framework import serializers
from django.utils import timezone
from .models import User, Attendance

class EmployeeListSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    current_attendance_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'name', 'email', 'department', 
            'designation', 'role', 'joining_date', 
            'current_attendance_status', 'salary_amount'
        ]

    def get_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_current_attendance_status(self, obj):
        today = timezone.localdate()
        # Look up prefetch/cached or query today's attendance
        attendance = obj.attendances.filter(date=today).first()
        return attendance.status if attendance else 'no_record'
