from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Attendance, AttendanceCorrectionRequest, CompanyHoliday, Department, Designation, EmployeeActivity, EmployeeDocument, LeaveApplication, LeavePolicy, PayrollTaxDocument, Project, ProjectAssignment, ProjectMilestone, ProjectResource, ProjectTask, ProjectTechnology, Salary, SalaryComponent, SalaryRevision, SalaryStructure, User


@admin.register(User)
class EmployeeUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Personal details', {'fields': ('gender', 'date_of_birth', 'personal_email', 'emergency_contact', 'phone_number', 'address', 'profile_photo')}),
        ('Employment details', {'fields': ('employee_id', 'role', 'employment_status', 'department', 'designation', 'manager', 'work_location', 'employment_type', 'joining_date', 'leave_entitlement_days', 'casual_leave_quota', 'sick_leave_quota', 'paid_leave_quota')}),
        ('Payroll details', {'fields': ('salary_amount', 'bank_account_number', 'bank_identifier', 'tax_id')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Employee details', {'fields': ('gender', 'role', 'employment_status', 'department', 'designation', 'manager', 'work_location', 'employment_type', 'joining_date', 'leave_entitlement_days', 'casual_leave_quota', 'sick_leave_quota', 'paid_leave_quota', 'salary_amount')}),
    )
    readonly_fields = ('employee_id',)


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


@admin.register(EmployeeActivity)
class EmployeeActivityAdmin(admin.ModelAdmin):
    list_display = ('employee', 'activity_type', 'actor', 'created_at')
    list_filter = ('activity_type', 'created_at')
    search_fields = ('employee__username', 'employee__first_name', 'employee__last_name', 'description')
    readonly_fields = ('employee', 'actor', 'activity_type', 'description', 'created_at')


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


@admin.register(LeavePolicy)
class LeavePolicyAdmin(admin.ModelAdmin):
    list_display = ('leave_type', 'annual_quota', 'is_paid', 'requires_document')
    list_filter = ('is_paid', 'requires_document')


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'head', 'parent_department', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'head__username', 'head__first_name', 'head__last_name')


@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'is_active')
    list_filter = ('department', 'is_active')
    search_fields = ('name', 'department__name')


@admin.register(SalaryStructure)
class SalaryStructureAdmin(admin.ModelAdmin):
    list_display = ('employee', 'basic_salary', 'hra', 'allowances', 'deductions', 'effective_from', 'is_active')
    list_filter = ('is_active', 'attendance_based')
    search_fields = ('employee__username', 'employee__first_name', 'employee__last_name')


@admin.register(SalaryRevision)
class SalaryRevisionAdmin(admin.ModelAdmin):
    list_display = ('structure', 'effective_from', 'basic_salary', 'hra', 'allowances', 'revised_by', 'created_at')
    list_filter = ('effective_from',)
    search_fields = ('structure__employee__username', 'reason')
    readonly_fields = (
        'structure',
        'basic_salary',
        'hra',
        'allowances',
        'deductions',
        'attendance_based',
        'effective_from',
        'reason',
        'revised_by',
        'created_at',
    )


class SalaryComponentInline(admin.TabularInline):
    model = SalaryComponent
    extra = 0


@admin.register(Salary)
class SalaryAdmin(admin.ModelAdmin):
    list_display = ('employee', 'year', 'month', 'amount', 'status', 'paid_date')
    list_filter = ('status', 'year', 'month')
    search_fields = ('employee__username', 'employee__first_name', 'employee__last_name')
    inlines = [SalaryComponentInline]


@admin.register(PayrollTaxDocument)
class PayrollTaxDocumentAdmin(admin.ModelAdmin):
    list_display = ('employee', 'financial_year', 'document_type', 'uploaded_at')
    list_filter = ('financial_year', 'document_type')
    search_fields = ('employee__username', 'employee__first_name', 'employee__last_name')
