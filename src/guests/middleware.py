from datetime import timedelta
from ipaddress import ip_address
from django.conf import settings
from django.db import models
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from .models import AuthRateLimit


class AuthRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST' and request.path in ('/admin/login/', '/cadastro/', '/admin/cadastro/'):
            signup = 'cadastro' in request.path
            limit = 10 if signup else 30
            now = timezone.now()
            window = timedelta(hours=1) if signup else timedelta(minutes=15)
            client_ip = request.META.get('REMOTE_ADDR', 'unknown')
            # Only enable this behind the controlled, loopback-bound proxy. That
            # proxy must overwrite or append the actual client address last.
            if settings.TRUST_PROXY and request.META.get('HTTP_X_FORWARDED_FOR'):
                try:
                    client_ip = str(ip_address(request.META['HTTP_X_FORWARDED_FOR'].split(',')[-1].strip()))
                except ValueError:
                    pass
            key = salted_hmac('auth-budget', f'{signup}:{client_ip}').hexdigest()
            budget, _ = AuthRateLimit.objects.get_or_create(key=key, defaults={'window_started': now})
            AuthRateLimit.objects.filter(pk=key, window_started__lt=now-window).update(count=0, window_started=now)
            AuthRateLimit.objects.filter(pk=key).update(count=models.F('count') + 1)
            budget.refresh_from_db()
            if budget.count > limit:
                response = TemplateResponse(request, 'registration/rate_limited.html', status=429)
                response['Retry-After'] = str(max(1, int((budget.window_started + window - now).total_seconds())))
                return response.render()
        return self.get_response(request)
