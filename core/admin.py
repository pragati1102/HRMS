from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Attendance, AttendanceCorrectionRequest, CompanyHoliday, EmployeeDocument, LeaveApplication, Project, ProjectAssignment, ProjectMilestone, ProjectResource, ProjectTask, ProjectTechnology, User


@admin.register(User)
class EmployeeUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Personal details', {'fields': ('gender', 'date_of_birth', 'personal_email', 'emergency_contact', 'phone_number', 'address', 'profile_photo')}),
        ('Employment details', {'fields': ('role', 'department', 'designation', 'manager', 'work_location', 'employment_type', 'joining_date', 'leave_entitlement_days', 'casual_leave_quota', 'sick_leave_quota', 'paid_leave_quota')}),
        ('Payroll details', {'fields': ('salary_amount', 'bank_account_number', 'bank_identifier', 'tax_id')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Employee details', {'fields': ('gender', 'role', 'department', 'designation', 'manager', 'work_location', 'employment_type', 'joining_date', 'leave_entitlement_days', 'casual_leave_quota', 'sick_leave_quota', 'paid_leave_quota', 'salary_amount')}),
    )


class ProjectAssignmentInline(admin.TabularInline):
    model = ProjectAssignment
    extra = 0


class ProjectMilestoneInline(admin.TabularInline):
    model = ProjectMilestone
    extra = 0


class ProjectTaskInline(admin.TabularInline):
    model = ProjectTask
    extra = 0


class ProjectTechnologyInline(admin.TabularInline):
    model = ProjectTechnology
    extra = 0


class ProjectResourceInline(admin.TabularInline):
    model = ProjectResource
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'status', 'start_date', 'end_date')
    list_filter = ('status',)
    search_fields = ('name', 'category', 'description')
    filter_horizontal = ('employees',)
    inlines = [
        ProjectAssignmentInline,
        ProjectMilestoneInline,
        ProjectTaskInline,
        ProjectTechnologyInline,
        ProjectResourceInline,
    ]


@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'employee', 'category', 'uploaded_at')
    list_filter = ('category', 'uploaded_at')
    search_fields = ('title', 'employee__username', 'employee__first_name', 'employee__last_name')


@admin.register(AttendanceCorrectionRequest)
class AttendanceCorrectionRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'requested_check_in', 'requested_check_out', 'status', 'created_at')
    list_filter = ('status', 'date')
    search_fields = ('employee__username', 'employee__first_name', 'employee__last_name', 'reason')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'status', 'check_in', 'check_out', 'location_mode', 'remarks')
    list_filter = ('status', 'location_mode', 'date')
    search_fields = ('employee__username', 'employee__first_name', 'employee__last_name', 'remarks')
    list_editable = ('remarks',)


@admin.register(CompanyHoliday)
class CompanyHolidayAdmin(admin.ModelAdmin):
    list_display = ('date', 'name')
    list_filter = ('date',)
    search_fields = ('name',)


@admin.register(LeaveApplication)
class LeaveApplicationAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'start_date', 'end_date', 'status', 'approved_by', 'applied_on')
    list_filter = ('status', 'leave_type', 'start_date')
    search_fields = ('employee__username', 'employee__first_name', 'employee__last_name', 'reason')
    readonly_fields = ('employee', 'start_date', 'end_date', 'reason', 'leave_type', 'half_day_session', 'supporting_document', 'handover_contact', 'applied_on')
    fields = ('employee', 'leave_type', 'start_date', 'end_date', 'half_day_session', 'reason', 'supporting_document', 'handover_contact', 'status', 'approved_by', 'approval_notes', 'applied_on')
