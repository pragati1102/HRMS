from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q

from core.models import (
    Department,
    Designation,
    EmployeeDocument,
    LeavePolicy,
    SalaryStructure,
    User,
)


class LeavePolicyForm(forms.ModelForm):
    class Meta:
        model = LeavePolicy
        fields = ['annual_quota', 'is_paid', 'requires_document']
        widgets = {
            'annual_quota': forms.NumberInput(attrs={'min': 0, 'placeholder': 'No limit'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = (
                    'form-select'
                    if isinstance(field.widget, forms.Select)
                    else 'form-control'
                )


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'description', 'head', 'parent_department', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['head'].queryset = User.objects.filter(
            Q(is_active=True) | Q(pk=self.instance.head_id),
            role='employee',
        ).order_by('first_name', 'last_name', 'username')
        self.fields['parent_department'].queryset = Department.objects.filter(
            Q(is_active=True) | Q(pk=self.instance.parent_department_id),
        ).exclude(pk=self.instance.pk)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = (
                    'form-select'
                    if isinstance(field.widget, forms.Select)
                    else 'form-control'
                )

    def clean(self):
        cleaned_data = super().clean()
        head = cleaned_data.get('head')
        parent = cleaned_data.get('parent_department')
        if head and self.instance.pk and head.department_record_id not in {
            None,
            self.instance.pk,
        }:
            self.add_error('head', 'The department head must belong to this department.')
        if parent and self.instance.pk:
            descendant_ids = set()
            pending = [self.instance.pk]
            while pending:
                parent_id = pending.pop()
                children = list(Department.objects.filter(
                    parent_department_id=parent_id,
                ).values_list('pk', flat=True))
                descendant_ids.update(children)
                pending.extend(children)
            if parent.pk in descendant_ids:
                self.add_error('parent_department', 'A department cannot be nested under its own descendant.')
        return cleaned_data


class DesignationForm(forms.ModelForm):
    class Meta:
        model = Designation
        fields = ['department', 'name', 'description', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = Department.objects.filter(
            Q(is_active=True) | Q(pk=self.instance.department_id),
        )
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = (
                    'form-select'
                    if isinstance(field.widget, forms.Select)
                    else 'form-control'
                )


class SalaryStructureForm(forms.ModelForm):
    reason = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Reason for this revision'}),
    )

    class Meta:
        model = SalaryStructure
        fields = [
            'employee',
            'basic_salary',
            'hra',
            'allowances',
            'deductions',
            'attendance_based',
            'effective_from',
            'is_active',
        ]
        widgets = {'effective_from': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = User.objects.filter(
            role='employee',
        ).order_by('first_name', 'last_name', 'username')
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = (
                    'form-select'
                    if isinstance(field.widget, forms.Select)
                    else 'form-control'
                )

    def clean(self):
        cleaned_data = super().clean()
        for field_name in ('basic_salary', 'hra', 'allowances', 'deductions'):
            if cleaned_data.get(field_name, 0) < 0:
                self.add_error(field_name, 'Salary components cannot be negative.')
        return cleaned_data


class EmployeeManagementForm(forms.ModelForm):
    department = forms.CharField(required=False, widget=forms.HiddenInput())
    designation = forms.CharField(required=False, widget=forms.HiddenInput())

    password = forms.CharField(
        label='Temporary password',
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'new-password',
        }),
        help_text='Required when creating an employee account.',
    )

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'username',
            'email',
            'personal_email',
            'phone_number',
            'gender',
            'date_of_birth',
            'address',
            'emergency_contact',
            'profile_photo',
            'department',
            'designation',
            'department_record',
            'designation_record',
            'manager',
            'joining_date',
            'employment_type',
            'employment_status',
            'work_location',
            'leave_entitlement_days',
            'casual_leave_quota',
            'sick_leave_quota',
            'paid_leave_quota',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'joining_date': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'manager': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_employment_status = self.instance.employment_status
        self.original_is_active = self.instance.is_active
        for field in self.fields.values():
            if not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs['class'] = (
                    'form-select'
                    if isinstance(field.widget, forms.Select)
                    else 'form-control'
                )
        self.fields['password'].widget.attrs['class'] = 'form-control'
        self.fields['manager'].queryset = User.objects.filter(is_active=True).order_by(
            'first_name', 'last_name', 'username'
        )
        self.fields['department_record'].queryset = Department.objects.filter(
            Q(is_active=True) | Q(pk=self.instance.department_record_id),
        )
        self.fields['designation_record'].queryset = Designation.objects.filter(
            (Q(department__is_active=True, is_active=True) | Q(pk=self.instance.designation_record_id)),
        ).select_related('department')
        self.fields['designation_record'].label_from_instance = (
            lambda designation: f'{designation.name} · {designation.department.name}'
        )
        self.fields['department_record'].label = 'Department'
        self.fields['designation_record'].label = 'Designation'
        self.fields['profile_photo'].help_text = 'JPG, PNG, or WEBP; maximum 5 MB.'
        self.fields['username'].help_text = 'Used by the employee to sign in.'

    def clean(self):
        cleaned_data = super().clean()
        if self.instance._state.adding and not cleaned_data.get('password'):
            self.add_error('password', 'Set a temporary password for the new account.')
        elif cleaned_data.get('password'):
            try:
                validate_password(cleaned_data['password'], self.instance)
            except ValidationError as error:
                self.add_error('password', error)
        if cleaned_data.get('profile_photo'):
            photo = cleaned_data['profile_photo']
            if photo.size > 5 * 1024 * 1024:
                self.add_error('profile_photo', 'Profile photos must be 5 MB or smaller.')
        if self.instance.pk and cleaned_data.get('manager'):
            if cleaned_data['manager'].pk == self.instance.pk:
                self.add_error('manager', 'An employee cannot report to themselves.')
        department = cleaned_data.get('department_record')
        designation = cleaned_data.get('designation_record')
        if designation and (not department or designation.department_id != department.pk):
            self.add_error('designation_record', 'Choose a designation belonging to the selected department.')
        return cleaned_data

    def save(self, commit=True):
        employee = super().save(commit=False)
        if not employee.department_record and self.cleaned_data.get('department'):
            employee.department_record, _ = Department.objects.get_or_create(
                name=self.cleaned_data['department'].strip(),
            )
        if (
            employee.department_record
            and not employee.designation_record
            and self.cleaned_data.get('designation')
        ):
            employee.designation_record, _ = Designation.objects.get_or_create(
                department=employee.department_record,
                name=self.cleaned_data['designation'].strip(),
            )
        if self.cleaned_data.get('password'):
            employee.set_password(self.cleaned_data['password'])
        employee.role = 'employee'
        employee.department = employee.department_record.name if employee.department_record else ''
        employee.designation = employee.designation_record.name if employee.designation_record else ''
        if self.instance._state.adding:
            employee.is_active = employee.employment_status in {'active', 'on_leave'}
        elif employee.employment_status != self.original_employment_status:
            employee.is_active = employee.employment_status in {'active', 'on_leave'}
        else:
            employee.is_active = self.original_is_active
        if commit:
            employee.save()
            self.save_m2m()
        return employee


class EmployeeDocumentForm(forms.ModelForm):
    class Meta:
        model = EmployeeDocument
        fields = ['title', 'category', 'file']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Signed offer letter'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = (
                'form-select'
                if isinstance(field.widget, forms.Select)
                else 'form-control'
            )

    def clean_file(self):
        uploaded_file = self.cleaned_data['file']
        if uploaded_file.size > 10 * 1024 * 1024:
            raise ValidationError('Documents must be 10 MB or smaller.')
        return uploaded_file
