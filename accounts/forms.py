from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from .models import User, MemberProfile, StaffProfile


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password',
        })
    )


class MemberRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create password'}),
        help_text="Minimum 8 characters."
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'})
    )
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'})
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Mailing address'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.role = User.ROLE_MEMBER
        if commit:
            user.save()
            MemberProfile.objects.create(
                user=user,
                membership_id=MemberProfile.generate_membership_id(),
                phone=self.cleaned_data.get('phone', ''),
                address=self.cleaned_data.get('address', '')
            )
        return user


class LibrarianMemberCreateForm(forms.ModelForm):
    """Used by librarian to register a new member in the library"""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Temporary Password'}),
        initial='library123'
    )
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'})
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Address'})
    )
    membership_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank to auto-generate'})
    )
    max_books_allowed = forms.IntegerField(
        initial=3,
        min_value=1,
        max_value=10,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_membership_id(self):
        mem_id = self.cleaned_data.get('membership_id')
        if mem_id and MemberProfile.objects.filter(membership_id=mem_id).exists():
            raise forms.ValidationError("A member with this Membership ID already exists.")
        return mem_id

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.role = User.ROLE_MEMBER
        if commit:
            user.save()
            mem_id = self.cleaned_data.get('membership_id') or MemberProfile.generate_membership_id()
            MemberProfile.objects.create(
                user=user,
                membership_id=mem_id,
                phone=self.cleaned_data.get('phone', ''),
                address=self.cleaned_data.get('address', ''),
                max_books_allowed=self.cleaned_data.get('max_books_allowed', 3)
            )
        return user


class MemberEditForm(forms.ModelForm):
    """Used by librarian to edit an existing member"""
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    max_books_allowed = forms.IntegerField(
        min_value=1,
        max_value=10,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    is_blocked = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'member_profile'):
            profile = self.instance.member_profile
            self.fields['phone'].initial = profile.phone
            self.fields['address'].initial = profile.address
            self.fields['max_books_allowed'].initial = profile.max_books_allowed
            self.fields['is_blocked'].initial = profile.is_blocked

    def save(self, commit=True):
        user = super().save(commit=commit)
        if hasattr(user, 'member_profile'):
            profile = user.member_profile
            profile.phone = self.cleaned_data.get('phone', '')
            profile.address = self.cleaned_data.get('address', '')
            profile.max_books_allowed = self.cleaned_data.get('max_books_allowed', 3)
            profile.is_blocked = self.cleaned_data.get('is_blocked', False)
            profile.save()
        return user


class UserProfileForm(forms.ModelForm):
    """Used by user to edit their own profile"""
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'member_profile'):
            profile = self.instance.member_profile
            self.fields['phone'].initial = profile.phone
            self.fields['address'].initial = profile.address

    def save(self, commit=True):
        user = super().save(commit=commit)
        if hasattr(user, 'member_profile'):
            profile = user.member_profile
            profile.phone = self.cleaned_data.get('phone', '')
            profile.address = self.cleaned_data.get('address', '')
            profile.save()
        return user


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class StaffCreateForm(forms.ModelForm):
    staff_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank to auto-generate (e.g. STF-1001)'}),
        help_text="Unique Staff ID. If left blank, one will be generated automatically."
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}),
        help_text="Minimum 8 characters."
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'})
    )
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'})
    )
    department = forms.CharField(
        required=False,
        initial='Circulation',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Department (e.g. Circulation, Cataloging)'})
    )
    is_active = forms.BooleanField(
        initial=True,
        required=False,
        label="Account Active",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'}),
        }

    def clean_staff_id(self):
        staff_id = self.cleaned_data.get('staff_id')
        if staff_id and StaffProfile.objects.filter(staff_id=staff_id).exists():
            raise forms.ValidationError("A staff member with this Staff ID already exists.")
        return staff_id

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.role = User.ROLE_STAFF
        user.is_staff = True
        user.is_superuser = False
        user.is_active = self.cleaned_data.get('is_active', True)
        if commit:
            user.save()
            staff_id = self.cleaned_data.get('staff_id') or StaffProfile.generate_staff_id()
            StaffProfile.objects.create(
                user=user,
                staff_id=staff_id,
                phone=self.cleaned_data.get('phone', ''),
                department=self.cleaned_data.get('department', 'Circulation')
            )
        return user


class StaffEditForm(forms.ModelForm):
    staff_id = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    department = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank to keep existing password'}),
        help_text="Leave blank unless you wish to reset the password."
    )
    is_active = forms.BooleanField(
        required=False,
        label="Account Active",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'staff_profile'):
            profile = self.instance.staff_profile
            self.fields['staff_id'].initial = profile.staff_id
            self.fields['phone'].initial = profile.phone
            self.fields['department'].initial = profile.department

    def clean_staff_id(self):
        staff_id = self.cleaned_data.get('staff_id')
        existing = StaffProfile.objects.filter(staff_id=staff_id)
        if self.instance and hasattr(self.instance, 'staff_profile'):
            existing = existing.exclude(pk=self.instance.staff_profile.pk)
        if existing.exists():
            raise forms.ValidationError("Another staff member already has this Staff ID.")
        return staff_id

    def save(self, commit=True):
        user = super().save(commit=commit)
        new_password = self.cleaned_data.get('new_password')
        if new_password:
            user.set_password(new_password)
            user.save()
        if hasattr(user, 'staff_profile'):
            profile = user.staff_profile
            profile.staff_id = self.cleaned_data.get('staff_id', profile.staff_id)
            profile.phone = self.cleaned_data.get('phone', '')
            profile.department = self.cleaned_data.get('department', 'Circulation')
            profile.save()
        else:
            StaffProfile.objects.create(
                user=user,
                staff_id=self.cleaned_data.get('staff_id') or StaffProfile.generate_staff_id(),
                phone=self.cleaned_data.get('phone', ''),
                department=self.cleaned_data.get('department', 'Circulation')
            )
        return user
