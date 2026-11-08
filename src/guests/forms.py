from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm
from .models import Attendance, Guest, User, normalize_phone, phone_variants
from .passwords import initial_responsible_password


class GuestAdminForm(forms.ModelForm):
    class Meta:
        model = Guest
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'family' in self.fields:
            self.fields['family'].required = False
            self.fields['family'].help_text = 'Opcional. Sem seleção, entra na família da conta logada. Convidados não precisam de telefone ou senha.'


class PhoneLoginForm(AuthenticationForm):
    username = forms.CharField(label='Telefone com DDD', widget=forms.TextInput(attrs={
        'type': 'tel', 'inputmode': 'tel', 'autocomplete': 'username', 'placeholder': '(24) 99999-9999',
    }))

    def clean_username(self):
        return normalize_phone(self.cleaned_data['username'])


class SignUpForm(forms.ModelForm):
    phone = forms.CharField(label='Telefone do responsável com DDD', help_text='Só o responsável precisa de telefone. Os demais familiares serão adicionados apenas pelo nome.', widget=forms.TextInput(attrs={
        'type': 'tel', 'inputmode': 'tel', 'autocomplete': 'tel', 'placeholder': '(24) 99999-9999',
    }))
    first_name = forms.CharField(label='Nome do responsável da família', max_length=150, widget=forms.TextInput(attrs={'autocomplete': 'name'}))

    class Meta:
        model = User
        fields = ('first_name', 'phone')

    def clean_phone(self):
        value = normalize_phone(self.cleaned_data['phone'])
        if User.objects.filter(phone__in=phone_variants(value)).exists():
            raise forms.ValidationError('Já existe uma conta com esse telefone. Entre com sua senha.')
        return value

    def clean_first_name(self):
        name = self.cleaned_data['first_name'].strip()
        if not name:
            raise forms.ValidationError('Informe seu nome.')
        return name

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(initial_responsible_password(self.cleaned_data['phone']))
        if commit:
            user.save()
            self.save_m2m()
        return user


class AdminUserChangeForm(UserChangeForm):
    def clean_phone(self):
        value = normalize_phone(self.cleaned_data['phone'])
        if User.objects.exclude(pk=self.instance.pk).filter(phone__in=phone_variants(value)).exists():
            raise forms.ValidationError('Esse telefone já está em uso.')
        return value

    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'


class ProfileForm(forms.ModelForm):
    def __init__(self, *args, can_change_phone=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['phone'].disabled = not can_change_phone
        if not can_change_phone:
            self.fields['phone'].help_text = 'Para alterar o telefone, entre em contato com a organização da festa.'

    class Meta:
        model = User
        fields = ('first_name', 'phone')
        widgets = {'first_name': forms.TextInput(attrs={'autocomplete': 'name'}), 'phone': forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel'})}

    def clean_phone(self):
        value = normalize_phone(self.cleaned_data['phone'])
        if User.objects.exclude(pk=self.instance.pk).filter(phone__in=phone_variants(value)).exists():
            raise forms.ValidationError('Esse telefone já está em uso.')
        return value


class AttendanceForm(forms.Form):
    attendance = forms.ChoiceField(choices=Attendance.choices)


def normalized_registration_name(value):
    import unicodedata
    normalized = ''.join(char for char in unicodedata.normalize('NFKD', value) if not unicodedata.combining(char))
    parts = normalized.casefold().split()
    treatments = {'tio', 'tia', 'vo', 'vovo', 'bisa', 'bisavo', 'padre', 'dinda', 'dindo', 'dindinha', 'dindinho'}
    while len(parts) > 1 and parts[0].rstrip('.') in treatments:
        parts.pop(0)
    return ' '.join(parts)


class ActivateAccountForm(forms.Form):
    first_name = forms.CharField(label='Nome do responsável da família', max_length=150, widget=forms.TextInput(attrs={'autocomplete': 'name'}))
    phone = forms.CharField(label='Telefone com DDD', max_length=40, widget=forms.TextInput(attrs={'type': 'tel', 'inputmode': 'tel', 'autocomplete': 'tel', 'placeholder': '(24) 99999-9999'}))
    password1 = forms.CharField(label='Senha', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    password2 = forms.CharField(label='Confirmação de senha', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))

    def clean_phone(self):
        return normalize_phone(self.cleaned_data['phone'])

    def clean(self):
        from django.contrib.auth.password_validation import validate_password
        cleaned = super().clean()
        self.account = None
        if cleaned.get('first_name') and cleaned.get('phone'):
            matches = list(User.objects.filter(phone__in=phone_variants(cleaned['phone']), is_active=True, is_superuser=False, is_staff=False, family__isnull=False)[:2])
            account = matches[0] if len(matches) == 1 else None
            if account and normalized_registration_name(account.first_name) == normalized_registration_name(cleaned['first_name']):
                self.account = account
            else:
                self.add_error(None, 'Pessoa não cadastrada. Confira o nome e o telefone ou entre em contato com a organização.')
        password = cleaned.get('password1')
        if password and cleaned.get('password2'):
            if password != cleaned['password2']:
                self.add_error('password2', 'As senhas não coincidem.')
            try:
                validate_password(password, user=self.account)
            except forms.ValidationError as exc:
                self.add_error('password2', exc)
        return cleaned

    def save(self):
        self.account.set_password(self.cleaned_data['password1'])
        self.account.save(update_fields=['password'])
        return self.account
