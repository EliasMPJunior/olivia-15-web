"""Bootstrap the organizer once, without changing existing accounts or passwords."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from guests.models import normalize_phone


def main():
    User = get_user_model()
    with transaction.atomic():
        if User.objects.filter(is_superuser=True, is_active=True).exists():
            print('Conta administrativa já existe; mantendo os dados e a senha.')
            return
        phone = os.getenv('DJANGO_ADMIN_PHONE') or ('+5524999999999' if settings.DEBUG else '')
        password = os.getenv('DJANGO_ADMIN_PASSWORD') or ('admin' if settings.DEBUG else '')
        name = os.getenv('DJANGO_ADMIN_NAME') or 'Administrador'
        if not phone or not password:
            raise RuntimeError('Defina DJANGO_ADMIN_PHONE e DJANGO_ADMIN_PASSWORD para criar a conta administrativa em produção.')
        phone = normalize_phone(phone)
        if User.objects.filter(phone=phone).exists():
            raise RuntimeError('O telefone administrativo já pertence a uma conta comum. Configure outro telefone; nenhuma conta será promovida automaticamente.')
        User.objects.create_superuser(phone=phone, password=password, first_name=name)
        print(f'Conta administrativa criada para {phone}.')


if __name__ == '__main__':
    main()
