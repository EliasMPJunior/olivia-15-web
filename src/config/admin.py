from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods, require_POST
from guests.forms import AttendanceForm, PhoneLoginForm, ProfileForm
from guests.models import Attendance, Guest


class OliviaAdminSite(admin.AdminSite):
    site_header = 'Olívia · 15 anos'
    site_title = 'Olívia 15'
    index_title = 'Minha lista'
    site_url = None
    enable_nav_sidebar = False
    login_form = PhoneLoginForm
    login_template = 'admin/login.html'
    logout_template = 'registration/logged_out.html'

    def has_permission(self, request):
        # The admin is the guest portal. Model/user administration stays protected
        # separately; a public account is never promoted to staff.
        return request.user.is_authenticated and request.user.is_active

    def get_urls(self):
        return [
            path('minha-presenca/', self.admin_view(self.own_attendance), name='own_attendance'),
            path('convidado/<uuid:pk>/presenca/', self.admin_view(self.guest_attendance), name='guest_attendance'),
            path('meu-perfil/', self.admin_view(self.profile), name='profile'),
        ] + super().get_urls()

    def index(self, request, extra_context=None):
        guests = Guest.objects.filter(family__responsible=request.user)
        counts = guests.aggregate(total=Count('pk'), confirmed=Count('pk', filter=Q(attendance=Attendance.YES)), pending=Count('pk', filter=Q(attendance=Attendance.PENDING)))
        confirmed = counts['confirmed'] + int(request.user.attendance == Attendance.YES)
        pending = counts['pending'] + int(request.user.attendance == Attendance.PENDING)
        context = {
            **self.each_context(request), 'title': 'Minha lista',
            'guests': guests, 'attendance_choices': Attendance.choices,
            'total_people': counts['total'] + 1, 'confirmed_people': confirmed, 'pending_people': pending,
            **(extra_context or {}),
        }
        request.current_app = self.name
        return TemplateResponse(request, 'admin/index.html', context)

    @method_decorator(require_POST)
    def own_attendance(self, request):
        form = AttendanceForm(request.POST)
        if not form.is_valid():
            return TemplateResponse(request, 'guests/invalid_response.html', {'title': 'Resposta inválida'}, status=400)
        request.user.attendance = form.cleaned_data['attendance']
        request.user.attendance_updated_at = timezone.now()
        request.user.save(update_fields=['attendance', 'attendance_updated_at'])
        messages.success(request, 'Sua presença foi atualizada.')
        return redirect('admin:index')

    @method_decorator(require_POST)
    def guest_attendance(self, request, pk):
        # Always scoped to the signed-in family responsible, even if a foreign UUID is supplied.
        guest = get_object_or_404(Guest, pk=pk, family__responsible=request.user)
        form = AttendanceForm(request.POST)
        if not form.is_valid():
            return TemplateResponse(request, 'guests/invalid_response.html', {'title': 'Resposta inválida'}, status=400)
        guest.attendance = form.cleaned_data['attendance']
        guest.attendance_updated_at = timezone.now()
        guest.save(update_fields=['attendance', 'attendance_updated_at'])
        messages.success(request, f'Presença de {guest.name} atualizada.')
        return redirect('admin:index')

    @method_decorator(require_http_methods(['GET', 'POST']))
    def profile(self, request):
        form = ProfileForm(request.POST or None, instance=request.user, can_change_phone=request.user.is_superuser)
        if request.method == 'POST' and form.is_valid():
            form.save()
            messages.success(request, 'Seu perfil foi atualizado.')
            return redirect('admin:index')
        request.current_app = self.name
        return TemplateResponse(request, 'guests/profile.html', {
            **self.each_context(request), 'title': 'Meu perfil', 'form': form,
        })
