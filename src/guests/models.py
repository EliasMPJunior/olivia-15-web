import re
import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings


def normalize_phone(value):
    """Accept Brazilian local numbers or an explicit international + prefix."""
    value = str(value or '').strip()
    if not value or re.search(r'[^\d\s()+.\-]', value):
        raise ValidationError('Informe um telefone válido com DDD.')
    digits = re.sub(r'\D', '', value)
    if value.startswith('+'):
        if not 10 <= len(digits) <= 15 or digits.startswith('0'):
            raise ValidationError('Informe um telefone válido com código do país.')
        return '+' + digits
    if len(digits) in (10, 11):
        if digits[0] == '0' or len(set(digits)) == 1:
            raise ValidationError('Informe um telefone válido com DDD.')
        return '+55' + digits
    if len(digits) in (12, 13) and digits.startswith('55'):
        return '+' + digits
    raise ValidationError('Informe um telefone com DDD, como (24) 99999-9999.')


class Attendance(models.TextChoices):
    PENDING = 'pending', 'Ainda não respondi'
    YES = 'yes', 'Vou à festa'
    NO = 'no', 'Não poderei ir'


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError('O telefone é obrigatório.')
        user = self.model(phone=normalize_phone(phone), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True or extra_fields.get('is_superuser') is not True:
            raise ValueError('Superusuários precisam de is_staff e is_superuser.')
        return self.create_user(phone, password, **extra_fields)


class User(AbstractUser):
    username = None
    first_name = models.CharField('nome completo', max_length=150)
    phone = models.CharField('telefone com DDD', max_length=16, unique=True)
    attendance = models.CharField('minha presença', max_length=7, choices=Attendance.choices, default=Attendance.PENDING)
    attendance_updated_at = models.DateTimeField('resposta atualizada em', null=True, blank=True)
    objects = UserManager()
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['first_name']

    class Meta:
        verbose_name = 'responsável da família'
        verbose_name_plural = 'responsáveis das famílias'

    def clean(self):
        super().clean()
        self.phone = normalize_phone(self.phone)

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.first_name or self.phone


class Family(models.Model):
    responsible = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='family', verbose_name='responsável da família')
    name = models.CharField('nome da família', max_length=150, blank=True, help_text='Opcional. Exemplo: Família Silva.')

    class Meta:
        verbose_name = 'família'
        verbose_name_plural = 'famílias'

    def __str__(self):
        return self.name or f'Família de {self.responsible}'


class Guest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='guests', verbose_name='família')
    name = models.CharField('nome do convidado', max_length=150)
    phone = models.CharField('telefone (opcional)', max_length=32, blank=True)
    attendance = models.CharField('presença', max_length=7, choices=[('pending', 'Aguardando resposta'), ('yes', 'Presença confirmada'), ('no', 'Não comparecerá')], default=Attendance.PENDING)
    attendance_updated_at = models.DateTimeField('resposta atualizada em', null=True, blank=True)
    created_at = models.DateTimeField('adicionado em', auto_now_add=True)

    class Meta:
        ordering = ('name',)
        verbose_name = 'convidado'
        verbose_name_plural = 'convidados'

    def __str__(self):
        return self.name


class AuthRateLimit(models.Model):
    """Persistent request budget, shared by Gunicorn workers without Redis."""
    key = models.CharField(max_length=64, primary_key=True)
    window_started = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)
