from django import forms
from django.core.exceptions import ValidationError
from .models import User


class EmployeeProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            'gender',
            'date_of_birth',
            'personal_email',
            'emergency_contact',
            'phone_number',
            'address',
            'profile_photo',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            field.widget.attrs['class'] = css_class

    def clean_profile_photo(self):
        photo = self.cleaned_data.get('profile_photo')
        if photo and photo.size > 5 * 1024 * 1024:
            raise ValidationError('Profile photos must be 5 MB or smaller.')
        return photo