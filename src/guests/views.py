from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .forms import ActivateAccountForm


@never_cache
@require_http_methods(['GET', 'POST'])
def signup(request):
    if request.user.is_authenticated:
        return redirect('admin:index')
    form = ActivateAccountForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, 'Senha salva. Confirme sua presença e a dos convidados da sua família!')
        return redirect('admin:index')
    return render(request, 'registration/signup.html', {'form': form, 'title': 'Cadastrar acesso'})
