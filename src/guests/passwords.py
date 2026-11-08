from .models import normalize_phone


def initial_responsible_password(phone):
    return '2026' + normalize_phone(phone)[-4:]
