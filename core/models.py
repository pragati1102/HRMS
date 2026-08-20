import calendar
import datetime
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('employee', 'Employee'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    department = models.CharField(max_length=100, blank=True, null=True)
    designation = models.CharField(max_length=100, blank=True, null=True)
    joining_date = models.DateField(blank=True, null=True)
    salary_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        full_name = self.get_full_name()
        return full_name if full_name else self.username

    @property
    def today_attendance_status(self):
        """
        Returns today's attendance status for the user, or 'no_record' if none exists.
        """
        today = timezone.localdate()
        att = self.attendances.filter(date=today).first()
        return att.status if att else 'no_record'

    def get_next_salary_due_date(self, reference_date=None):
        """
        Calculates the next salary due date for an employee based on their joining_date.
        
        Logic: 
        Salary is due on the same day-of-month as their joining_date, every month.
        
        Edge cases:
        If joining day is 29, 30, or 31, and a month doesn't have that many days,
        the date falls back to the last day of that month.
        
        Parameters:
        - reference_date (datetime.date): The date to calculate the next due date from.
                                          Defaults to today.
                                          
        Returns:
        - datetime.date: The next salary due date, or None if joining_date is not set.
        """
        if not self.joining_date:
            return None
            
        if reference_date is None:
            reference_date = timezone.localdate()
            
        joining_day = self.joining_date.day
        
        # Candidate 1: The current month and year of the reference date
        candidate_year = reference_date.year
        candidate_month = reference_date.month
        
        # Handle month-end fallback
        max_days = calendar.monthrange(candidate_year, candidate_month)[1]
        due_day = min(joining_day, max_days)
        candidate_due = datetime.date(candidate_year, candidate_month, due_day)
        
        # If the candidate date is today or in the future, it is the next due date
        if candidate_due >= reference_date:
            return candidate_due
            
        # Candidate 2: The next month
        if candidate_month == 12:
            next_month = 1
            next_year = candidate_year + 1
        else:
            next_month = candidate_month + 1
            next_year = candidate_year
            
        max_days_next = calendar.monthrange(next_year, next_month)[1]
        due_day_next = min(joining_day, max_days_next)
        return datetime.date(next_year, next_month, due_day_next)


class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('leave', 'Leave'),
        ('half_day', 'Half Day'),
    ]
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)

    class Meta:
        unique_together = ('employee', 'date')

    def __str__(self):
        return f"{self.employee.username} - {self.date} - {self.status} (In: {self.check_in or '-'}, Out: {self.check_out or '-'})"


class WorkLog(models.Model):
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='work_logs')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    hours_worked = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    description = models.TextField()
    CATEGORY_CHOICES = [
        ('Meeting', 'Meeting'),
        ('Development', 'Development'),
        ('Bug Fix', 'Bug Fix'),
        ('Documentation', 'Documentation'),
        ('Testing', 'Testing'),
        ('Other', 'Other'),
    ]
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Other')

    def __str__(self):
        return f"{self.employee.username} - {self.date} ({self.start_time} - {self.end_time}) - {self.hours_worked} hrs"

    def save(self, *args, **kwargs):
        # Auto-compute hours worked based on start_time and end_time
        if self.start_time and self.end_time:
            dummy_date = datetime.date(2000, 1, 1)
            dt_start = datetime.datetime.combine(dummy_date, self.start_time)
            dt_end = datetime.datetime.combine(dummy_date, self.end_time)
            
            # If end_time is earlier than start_time, assume it rolls over to next day
            if dt_end < dt_start:
                dt_end += datetime.timedelta(days=1)
                
            diff = dt_end - dt_start
            self.hours_worked = round(diff.total_seconds() / 3600.0, 2)
        super().save(*args, **kwargs)


class LeaveApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leave_applications')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    LEAVE_TYPE_CHOICES = [
        ('Sick', 'Sick'),
        ('Casual', 'Casual'),
        ('Paid', 'Paid'),
    ]
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES, default='Casual')
    applied_on = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_leaves'
    )

    def __str__(self):
        return f"{self.employee.username}: {self.start_date} to {self.end_date} ({self.status})"


class Project(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
    ]
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    employees = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='projects', blank=True)

    def __str__(self):
        return self.name


class Salary(models.Model):
    STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
    ]
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='salaries')
    month = models.IntegerField()
    year = models.IntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    paid_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ('employee', 'month', 'year')

    def __str__(self):
        return f"{self.employee.username} - {self.year}/{self.month:02d} - {self.status}"
