import calendar
import datetime
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.utils import timezone

class User(AbstractUser):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('employee', 'Employee'),
    ]
    EMPLOYMENT_TYPE_CHOICES = [
        ('full_time', 'Full-time'),
        ('part_time', 'Part-time'),
        ('contract', 'Contract'),
        ('intern', 'Intern'),
    ]
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    department = models.CharField(max_length=100, blank=True, null=True)
    designation = models.CharField(max_length=100, blank=True, null=True)
    joining_date = models.DateField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    personal_email = models.EmailField(blank=True)
    emergency_contact = models.CharField(max_length=30, blank=True)
    manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='direct_reports')
    work_location = models.CharField(max_length=150, blank=True)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, blank=True)
    leave_entitlement_days = models.PositiveSmallIntegerField(null=True, blank=True)
    casual_leave_quota = models.PositiveSmallIntegerField(null=True, blank=True)
    sick_leave_quota = models.PositiveSmallIntegerField(null=True, blank=True)
    paid_leave_quota = models.PositiveSmallIntegerField(null=True, blank=True)
    bank_account_number = models.CharField(max_length=40, blank=True)
    bank_identifier = models.CharField(max_length=40, blank=True)
    tax_id = models.CharField(max_length=40, blank=True)
    profile_photo = models.ImageField(
        upload_to='employee_photos/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
    )
    profile_updated_at = models.DateTimeField(null=True, blank=True)
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
    LOCATION_MODE_CHOICES = [
        ('office', 'Office'),
        ('remote', 'Remote / Work from Home'),
    ]
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
    break_seconds = models.PositiveIntegerField(default=0)
    break_started_at = models.DateTimeField(null=True, blank=True)
    location_mode = models.CharField(max_length=20, choices=LOCATION_MODE_CHOICES, blank=True)
    check_in_ip = models.GenericIPAddressField(null=True, blank=True)
    remarks = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ('employee', 'date')

    def __str__(self):
        return f"{self.employee.username} - {self.date} - {self.status} (In: {self.check_in or '-'}, Out: {self.check_out or '-'})"


class AttendanceCorrectionRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attendance_corrections')
    date = models.DateField()
    requested_check_in = models.TimeField(null=True, blank=True)
    requested_check_out = models.TimeField(null=True, blank=True)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.username} - {self.date} ({self.status})"


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
        ('withdrawn', 'Withdrawn'),
    ]
    HALF_DAY_CHOICES = [
        ('full', 'Full Day'),
        ('first_half', 'Half Day (First Half)'),
        ('second_half', 'Half Day (Second Half)'),
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
        ('Maternity', 'Maternity'),
        ('Paternity', 'Paternity'),
    ]
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES, default='Casual')
    half_day_session = models.CharField(max_length=20, choices=HALF_DAY_CHOICES, default='full')
    supporting_document = models.FileField(
        upload_to='leave_documents/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
    )
    handover_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leave_handovers',
    )
    approval_notes = models.TextField(blank=True)
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


class CompanyHoliday(models.Model):
    date = models.DateField(unique=True)
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f"{self.name} ({self.date})"


class Project(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
    ]
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, default='General')
    description = models.TextField(blank=True)
    objective = models.TextField(blank=True)
    goals = models.TextField(blank=True)
    scope = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    employees = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='projects', blank=True)

    def __str__(self):
        return self.name


class ProjectAssignment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='assignments')
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='project_assignments')
    role = models.CharField(max_length=120, default='Contributor')
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('project', 'employee')

    def __str__(self):
        return f'{self.employee} - {self.project} ({self.role})'


class ProjectMilestone(models.Model):
    STATUS_CHOICES = [
        ('done', 'Done'),
        ('in_progress', 'In Progress'),
        ('pending', 'Pending'),
    ]
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'due_date', 'id']

    def __str__(self):
        return f'{self.project}: {self.title}'


class ProjectTask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='project_tasks')
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['due_date', 'title']

    def __str__(self):
        return f'{self.project}: {self.title}'


class ProjectTechnology(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='technologies')
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ['name']
        unique_together = ('project', 'name')

    def __str__(self):
        return self.name


class ProjectResource(models.Model):
    RESOURCE_TYPES = [
        ('prd', 'PRD'),
        ('design', 'Design Specs'),
        ('repository', 'Repository'),
        ('documentation', 'Documentation'),
        ('other', 'Other'),
    ]
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='resources')
    title = models.CharField(max_length=150)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES, default='other')
    url = models.URLField(max_length=500)

    class Meta:
        ordering = ['resource_type', 'title']

    def __str__(self):
        return f'{self.project}: {self.title}'


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


class EmployeeDocument(models.Model):
    CATEGORY_CHOICES = [
        ('offer_letter', 'Offer Letter'),
        ('contract', 'Contract'),
        ('identity', 'Identity Proof'),
        ('tax', 'Tax Document'),
        ('other', 'Other'),
    ]
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    file = models.FileField(
        upload_to='employee_documents/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg'])],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.employee.username} - {self.title}"
