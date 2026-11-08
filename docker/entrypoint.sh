#!/usr/bin/env sh
set -eu
python manage.py migrate --noinput
python ensure_superuser.py
python manage.py collectstatic --noinput
if [ "${DJANGO_DEBUG:-0}" = "1" ]; then
  exec python manage.py runserver 0.0.0.0:8000
fi
# One worker keeps the SQLite write workload modest; threaded reads remain available.
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 1 --threads 4 --timeout 60 --access-logfile -
