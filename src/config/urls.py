from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import path
from django.views.decorators.http import require_GET
from guests.views import signup


@require_GET
def health(request):
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('', lambda request: redirect('admin:index')),
    path('cadastro/', signup, name='signup'),
    path('admin/cadastro/', signup),
    path('admin/', admin.site.urls),
    path('api/health/', health, name='health'),
]
