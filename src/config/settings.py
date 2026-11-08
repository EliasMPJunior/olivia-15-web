import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv('DJANGO_DEBUG', '0') == '1'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'local-development-only' if DEBUG else '')
if not SECRET_KEY and not DEBUG:
    secret_file = os.getenv('DJANGO_SECRET_KEY_FILE')
    if secret_file and Path(secret_file).is_file():
        SECRET_KEY = Path(secret_file).read_text(encoding='utf-8').strip()
if not SECRET_KEY:
    raise RuntimeError('Defina DJANGO_SECRET_KEY ou inicialize o arquivo DJANGO_SECRET_KEY_FILE para executar em produção.')
ALLOWED_HOSTS = [value.strip() for value in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]').split(',') if value.strip()]
CSRF_TRUSTED_ORIGINS = [value.strip() for value in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if value.strip()]
INSTALLED_APPS = [
    'config.apps.OliviaAdminConfig', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'guests.apps.GuestsConfig',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware',
    'guests.middleware.AuthRateLimitMiddleware', 'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages', 'guests.context_processors.invitation',
    ]},
}]
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': os.getenv('DJANGO_DB_PATH', str(BASE_DIR / 'db.sqlite3')),
    'OPTIONS': {'timeout': 20},
}}
AUTH_USER_MODEL = 'guests.User'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
]
LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/admin/'
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SECURE_SSL_REDIRECT = not DEBUG and os.getenv('DJANGO_SSL_REDIRECT', '1') == '1'
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
TRUST_PROXY = os.getenv('DJANGO_TRUST_PROXY', '0') == '1'
if TRUST_PROXY:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
INVITATION_URL = os.getenv('INVITATION_URL', 'https://olivia.brasidata.com.br/menu.html')
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
