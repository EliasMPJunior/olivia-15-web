from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import Group
from django.utils import timezone
from .forms import AdminUserChangeForm, GuestAdminForm, SignUpForm
from .models import Family, Guest, User


@admin.register(User)
class AccountAdmin(UserAdmin):
    add_form = SignUpForm
    form = AdminUserChangeForm
    list_display = ('first_name', 'phone', 'attendance', 'is_active', 'is_superuser')
    ordering = ('first_name',)
    search_fields = ('first_name', 'phone')
    readonly_fields = ('date_joined', 'last_login', 'attendance_updated_at')
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Perfil', {'fields': ('first_name', 'attendance', 'attendance_updated_at')}),
        ('Acesso', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Datas', {'fields': ('date_joined', 'last_login')}),
    )
    add_fieldsets = ((None, {'classes': ('wide',), 'fields': ('first_name', 'phone', 'password1', 'password2')}),)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        if not change or 'attendance' in form.changed_data:
            obj.attendance_updated_at = timezone.now()
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        if '_continue' in request.POST or '_addanother' in request.POST:
            return super().response_add(request, obj, post_url_continue)
        from django.shortcuts import redirect
        return redirect('admin:guests_family_change', obj.family.pk)


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    form = GuestAdminForm
    list_display = ('name', 'attendance', 'attendance_updated_at')
    list_filter = ('attendance',)
    search_fields = ('name',)
    readonly_fields = ('created_at', 'attendance_updated_at')
    list_per_page = 30

    def get_fields(self, request, obj=None):
        fields = ['name', 'attendance']
        if request.user.is_superuser:
            fields.insert(0, 'family')
        if obj:
            fields += ['attendance_updated_at', 'created_at']
        return fields

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset if request.user.is_superuser else queryset.filter(family__responsible=request.user)

    def has_module_permission(self, request):
        return request.user.is_active

    def has_add_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and (obj is None or request.user.is_superuser or obj.family.responsible_id == request.user.pk)

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    has_delete_permission = has_change_permission

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            raise PermissionDenied
        if not obj.family_id:
            obj.family_id = Guest.objects.only('family_id').get(pk=obj.pk).family_id if change else request.user.family.pk
        if not change or 'attendance' in form.changed_data:
            obj.attendance_updated_at = timezone.now()
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        if '_continue' in request.POST or '_addanother' in request.POST:
            return super().response_add(request, obj, post_url_continue)
        from django.shortcuts import redirect
        return redirect('admin:index')

    def response_change(self, request, obj):
        if '_continue' in request.POST or '_addanother' in request.POST:
            return super().response_change(request, obj)
        from django.shortcuts import redirect
        return redirect('admin:index')

    def response_delete(self, request, obj_display, obj_id):
        from django.shortcuts import redirect
        return redirect('admin:index')


# Groups are not useful for the guest-facing portal, even for ordinary staff.
admin.site.unregister(Group)


class FamilyGuestInline(admin.TabularInline):
    model = Guest
    fields = ('name', 'attendance')
    extra = 1
    verbose_name = 'convidado da família (sem telefone ou conta)'
    verbose_name_plural = 'convidados da família — informe apenas nome e presença'

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset if request.user.is_superuser else queryset.filter(family__responsible=request.user)

    def has_add_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    has_change_permission = has_add_permission
    def has_view_permission(self, request, obj=None):
        return request.user.is_active and (obj is None or request.user.is_superuser or obj.responsible_id == request.user.pk)
    has_delete_permission = has_add_permission


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    inlines = [FamilyGuestInline]
    list_display = ('__str__', 'responsible')
    search_fields = ('name', 'responsible__first_name')

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related('responsible')
        return queryset if request.user.is_superuser else queryset.filter(responsible=request.user)

    def get_fields(self, request, obj=None):
        return ['name', 'responsible'] if request.user.is_superuser else ['name']

    def get_readonly_fields(self, request, obj=None):
        return ['responsible']

    def has_module_permission(self, request):
        return request.user.is_active

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and (obj is None or request.user.is_superuser or obj.responsible_id == request.user.pk)

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return False  # A family's account creates it automatically, once.

    def has_delete_permission(self, request, obj=None):
        return False

    def save_formset(self, request, form, formset, change):
        if not request.user.is_superuser:
            raise PermissionDenied
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        for instance in instances:
            if not instance.pk or instance._state.adding or 'attendance' in next((f.changed_data for f in formset.forms if f.instance is instance), []):
                instance.attendance_updated_at = timezone.now()
            instance.family = form.instance
            instance.save()
        formset.save_m2m()
