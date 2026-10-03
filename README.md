# Antigravity HRMS

Django 6.1 + Django REST Framework HRMS. `core` contains the custom user, attendance, work logs, leave, salary, project, and employee self-service features. `admin_dashboard` provides role-protected admin pages, employee management, leave approvals, and workforce analytics. SQLite is configured for local development.

## Employee management

From **Admin → Employees**, administrators can create and update employee profiles, assign managers and employment statuses, manage profile photos and employee documents, review HR activity, and deactivate or reactivate sign-in access. Employee IDs are generated as `EMP` plus the employee's six-digit database ID. The directory supports search, department/status/account filters, sorting, and pagination.

Employee and document changes are recorded in the employee profile activity timeline. Employee documents are downloaded through an admin-protected view and are limited to 10 MB.

## Organization and payroll

**Organization** manages active/inactive departments, department heads, parent-department hierarchy, and department-scoped designations. Employee records keep the existing department/designation labels for API and dashboard compatibility and link them to managed organization records. The migration converts existing labels to department/designation records.

**Payroll** is restricted to administrators. Configure an employee's basic salary, HRA, allowances, deductions, attendance-proration setting, and effective date in a salary structure; each save creates an effective-dated revision. Preparing a monthly payroll snapshots the applicable revision and its components. With attendance proration enabled, recorded Absent/Half Day entries and approved Unpaid leave reduce pay, while approved paid leave does not; absent attendance records are not inferred from missing punches. Payroll rows are idempotent per employee/month, can be marked paid, exported as a CSV report, and generate PDFs available to the employee for their own paid records or to HR administrators.

## Attendance and leave management

Employees can check in/out, track breaks, view attendance history and the monthly attendance calendar, export their own attendance, and request attendance corrections. Administrators and managers can use **Attendance Register** to review the daily register, missing punches, monthly team totals, CSV reports, and pending regularizations. Managers only see and approve requests from their active direct reports.

Leave applications support Casual, Sick, Paid, Earned, Unpaid, Maternity, and Paternity leave, half days, weekday/holiday-aware balances, overlap validation, supporting documents, withdrawal, and cancellation of future approved leave. Administrators can review requests with comments, view the team leave/holiday calendar, and configure quotas, paid status, and document requirements from **Leave Policies**. An employee-specific Casual, Sick, or Paid quota takes precedence over the global policy quota.

In local development, leave-decision emails are written to the console. To use SMTP, configure `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` or `EMAIL_USE_SSL`, and `DEFAULT_FROM_EMAIL` as environment variables.

Apply database changes before starting the app:

```powershell
python manage.py migrate
```
