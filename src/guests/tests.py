from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from .models import Attendance, AuthRateLimit, Family, Guest, normalize_phone

User = get_user_model()
PASSWORD = 'Aurora!42MoonRiver'

class PortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user('24988880001', PASSWORD, first_name='Alice')
        cls.bia = User.objects.create_user('24988880002', PASSWORD, first_name='Beatriz')
        cls.organizer = User.objects.create_superuser('24988880003', PASSWORD, first_name='Organização')
        cls.own = Guest.objects.create(family=cls.alice.family, name='Convidado da Alice')
        cls.foreign = Guest.objects.create(family=cls.bia.family, name='Convidado da Beatriz')

    def login(self, user=None):
        self.client.force_login(user or self.alice)

    def test_anonymous_and_signup_routes(self):
        self.assertRedirects(self.client.get('/'), '/admin/', fetch_redirect_response=False)
        self.assertIn('/admin/login/', self.client.get('/admin/').url)
        self.assertEqual(self.client.get('/cadastro/').status_code, 200)
        self.assertEqual(self.client.get('/admin/cadastro/').status_code, 200)

    def test_phone_login_without_staff(self):
        r = self.client.post('/admin/login/', {'username': '(24) 98888-0001', 'password': PASSWORD, 'next': '/admin/'})
        self.assertRedirects(r, '/admin/')
        self.assertFalse(self.alice.is_staff)
        self.assertContains(self.client.get('/admin/'), self.own.name)

    def test_wrong_password(self):
        r = self.client.post('/admin/login/', {'username': self.alice.phone, 'password': 'wrong'})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_registration_updates_existing_account_without_creating_or_escalating(self):
        count = User.objects.count()
        family_id = self.alice.family.pk
        r = self.client.post('/cadastro/', {'first_name': 'Alice', 'phone': '(24) 98888-0001', 'password1': 'Changed!Aurora123', 'password2': 'Changed!Aurora123', 'is_staff': '1', 'is_superuser': '1', 'attendance': 'yes'})
        self.assertRedirects(r, '/admin/')
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password('Changed!Aurora123'))
        self.assertFalse(self.alice.is_staff)
        self.assertFalse(self.alice.is_superuser)
        self.assertEqual(User.objects.count(), count)
        self.assertEqual(self.alice.family.pk, family_id)
        self.assertEqual(self.alice.attendance, Attendance.PENDING)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.alice.pk)

    def test_signup_validates_phone_and_password(self):
        for phone in ('', 'abc', '123'):
            r = self.client.post('/cadastro/', {'first_name': 'Ana', 'phone': phone, 'password1': PASSWORD, 'password2': PASSWORD})
            self.assertIn('phone', r.context['form'].errors)
        r = self.client.post('/cadastro/', {'first_name': 'Ana', 'phone': '24999991234', 'password1': '12345678', 'password2': '12345678'})
        self.assertIn('password2', r.context['form'].errors)

    def test_duplicate_normalized_phone(self):
        r = self.client.post('/cadastro/', {'first_name': 'Outra pessoa', 'phone': '(24) 98888-0001', 'password1': PASSWORD, 'password2': PASSWORD})
        self.assertContains(r, 'Pessoa não cadastrada')
        self.assertEqual(User.objects.filter(phone=self.alice.phone).count(), 1)
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password(PASSWORD))

    def test_dashboard_and_native_list_are_private(self):
        self.login()
        for path in ('/admin/', reverse('admin:guests_guest_changelist')):
            r = self.client.get(path)
            self.assertContains(r, self.own.name)
            self.assertNotContains(r, self.foreign.name)
            self.assertNotContains(r, self.foreign.pk)
            self.assertNotContains(r, self.bia.phone)

    def test_foreign_edit_delete_history_are_inaccessible(self):
        self.login()
        for action in ('change', 'delete', 'history'):
            url = reverse(f'admin:guests_guest_{action}', args=[self.foreign.pk])
            r = self.client.get(url, follow=True)
            self.assertNotContains(r, self.foreign.name, status_code=r.status_code)
            self.client.post(url, {'name': 'hacked', 'attendance': 'yes', 'post': 'yes'})
        self.foreign.refresh_from_db()
        self.assertEqual(self.foreign.name, 'Convidado da Beatriz')
        self.assertEqual(self.foreign.attendance, Attendance.PENDING)

    def test_foreign_rsvp_and_get_mutations_are_blocked(self):
        self.login()
        self.assertEqual(self.client.post(reverse('admin:guest_attendance', args=[self.foreign.pk]), {'attendance': 'yes'}).status_code, 404)
        self.assertEqual(self.client.get(reverse('admin:guest_attendance', args=[self.own.pk])).status_code, 405)
        self.assertEqual(self.client.get(reverse('admin:own_attendance')).status_code, 405)

    def test_self_and_guest_responses_are_independent(self):
        self.login()
        self.client.post(reverse('admin:own_attendance'), {'attendance': 'yes'})
        self.client.post(reverse('admin:guest_attendance', args=[self.own.pk]), {'attendance': 'no'})
        self.alice.refresh_from_db(); self.own.refresh_from_db()
        self.assertEqual(self.alice.attendance, Attendance.YES)
        self.assertEqual(self.own.attendance, Attendance.NO)
        self.assertIsNotNone(self.alice.attendance_updated_at)
        self.assertIsNotNone(self.own.attendance_updated_at)
        r = self.client.get('/admin/')
        self.assertEqual(r.context['total_people'], 2)
        self.assertEqual(r.context['confirmed_people'], 1)
        self.assertEqual(r.context['pending_people'], 0)
        self.client.post(reverse('admin:own_attendance'), {'attendance': 'no'})
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.attendance, Attendance.NO)

    def test_invalid_response_is_rejected(self):
        self.login()
        self.assertEqual(self.client.post(reverse('admin:own_attendance'), {'attendance': 'invalid'}).status_code, 400)
        self.assertEqual(self.client.post(reverse('admin:guest_attendance', args=[self.own.pk]), {'attendance': 'invalid'}).status_code, 400)
        self.own.refresh_from_db()
        self.assertEqual(self.own.attendance, Attendance.PENDING)

    def test_responsible_cannot_create_edit_or_delete_guests(self):
        self.login()
        original_name = self.own.name
        routes = [
            (reverse('admin:guests_guest_add'), {'name': 'Não permitido', 'attendance': 'yes', 'family': self.alice.family.pk}),
            (reverse('admin:guests_guest_change', args=[self.own.pk]), {'name': 'Nome alterado', 'attendance': 'no', '_save': 'Salvar'}),
            (reverse('admin:guests_guest_delete', args=[self.own.pk]), {'post': 'yes'}),
        ]
        for url, payload in routes:
            self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.assertEqual(self.client.get(reverse('admin:guests_guest_add')).status_code, 403)
        self.own.refresh_from_db()
        self.assertEqual(self.own.name, original_name)
        self.assertEqual(self.own.attendance, Attendance.PENDING)
        self.assertFalse(Guest.objects.filter(name='Não permitido').exists())
        dashboard = self.client.get('/admin/')
        self.assertNotContains(dashboard, 'Adicionar convidado')
        self.assertNotContains(dashboard, 'aria-label="Editar ')

    def test_superuser_can_create_edit_and_delete_family_guests(self):
        self.login(self.organizer)
        r = self.client.post(reverse('admin:guests_guest_add'), {'name': 'Novo convidado', 'attendance': 'yes', 'family': self.alice.family.pk, '_save': 'Salvar'})
        self.assertRedirects(r, '/admin/')
        guest = Guest.objects.get(name='Novo convidado')
        self.assertEqual(guest.family.responsible, self.alice)
        r = self.client.post(reverse('admin:guests_guest_change', args=[guest.pk]), {'name': 'Nome corrigido', 'attendance': 'no', 'family': self.alice.family.pk, '_save': 'Salvar'})
        self.assertRedirects(r, '/admin/')
        guest.refresh_from_db()
        self.assertEqual(guest.name, 'Nome corrigido')
        self.client.post(reverse('admin:guests_guest_delete', args=[guest.pk]), {'post': 'yes'})
        self.assertFalse(Guest.objects.filter(pk=guest.pk).exists())

    def test_responsible_cannot_bulk_delete_any_guests(self):
        self.login()
        self.client.post(reverse('admin:guests_guest_changelist'), {'action': 'delete_selected', '_selected_action': [str(self.own.pk), str(self.foreign.pk)], 'post': 'yes'})
        self.assertTrue(Guest.objects.filter(pk=self.foreign.pk).exists())
        self.assertTrue(Guest.objects.filter(pk=self.own.pk).exists())

    def test_account_admin_requires_superuser(self):
        self.login()
        for path in (reverse('admin:guests_user_changelist'), reverse('admin:guests_user_add'), reverse('admin:guests_user_change', args=[self.alice.pk]), reverse('admin:auth_user_password_change', args=[self.bia.pk])):
            self.assertEqual(self.client.get(path).status_code, 403)
        self.login(self.organizer)
        self.assertContains(self.client.get(reverse('admin:guests_user_changelist')), self.alice.phone)
        r = self.client.get(reverse('admin:guests_guest_changelist'))
        self.assertContains(r, self.own.name)
        self.assertContains(r, self.foreign.name)

    def test_superuser_can_create_accounts(self):
        self.login(self.organizer)
        r = self.client.post(reverse('admin:guests_user_add'), {'first_name': 'Conta criada pela organização', 'phone': '24999995555', 'password1': PASSWORD, 'password2': PASSWORD, '_save': 'Salvar'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.get(phone='+5524999995555').check_password(PASSWORD))

    def test_profile_only_updates_public_fields(self):
        self.login()
        r = self.client.post(reverse('admin:profile'), {'first_name': 'Nome atualizado', 'phone': '(24) 99999-5678', 'is_superuser': '1', 'attendance': 'yes'})
        self.assertRedirects(r, '/admin/')
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.phone, '+5524988880001')
        self.assertFalse(self.alice.is_superuser)
        self.assertEqual(self.alice.attendance, Attendance.PENDING)
        r = self.client.post(reverse('admin:profile'), {'first_name': 'Alice', 'phone': self.bia.phone})
        self.assertRedirects(r, '/admin/')
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.phone, '+5524988880001')
        form = self.client.get(reverse('admin:profile')).context['form']
        self.assertTrue(form.fields['phone'].disabled)

    def test_superuser_can_update_phone_and_duplicate_is_rejected(self):
        self.login(self.organizer)
        r = self.client.post(reverse('admin:profile'), {'first_name': 'Organização', 'phone': '(24) 99999-5678'})
        self.assertRedirects(r, '/admin/')
        self.organizer.refresh_from_db()
        self.assertEqual(self.organizer.phone, '+5524999995678')
        r = self.client.post(reverse('admin:profile'), {'first_name': 'Organização', 'phone': self.bia.phone})
        self.assertIn('phone', r.context['form'].errors)
        r = self.client.post(reverse('admin:guests_user_change', args=[self.alice.pk]), {'first_name': self.alice.first_name, 'phone': '(24) 99999-3333', 'attendance': self.alice.attendance, 'is_active': 'on', '_save': 'Salvar'})
        self.assertEqual(r.status_code, 302)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.phone, '+5524999993333')

    def test_password_change_and_post_only_logout(self):
        self.login()
        self.assertEqual(self.client.get(reverse('admin:password_change')).status_code, 200)
        r = self.client.post(reverse('admin:password_change'), {'old_password': PASSWORD, 'new_password1': 'Another!42Aurora', 'new_password2': 'Another!42Aurora'})
        self.assertEqual(r.status_code, 302)
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password('Another!42Aurora'))
        self.assertEqual(self.client.get(reverse('admin:logout')).status_code, 405)
        self.assertEqual(self.client.post(reverse('admin:logout')).status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_csrf_on_public_forms_and_responses(self):
        c = Client(enforce_csrf_checks=True)
        self.assertEqual(c.post('/cadastro/', {}).status_code, 403)
        self.assertEqual(c.post('/admin/login/', {}).status_code, 403)
        c.force_login(self.alice)
        self.assertEqual(c.post(reverse('admin:own_attendance'), {'attendance': 'yes'}).status_code, 403)
        self.assertEqual(c.post(reverse('admin:guest_attendance', args=[self.own.pk]), {'attendance': 'yes'}).status_code, 403)
        r = c.get('/admin/')
        self.assertEqual(c.post(reverse('admin:own_attendance'), {'attendance': 'yes', 'csrfmiddlewaretoken': r.context['csrf_token']}).status_code, 302)

    def test_inactive_user_cannot_login(self):
        self.alice.is_active = False; self.alice.save()
        r = self.client.post('/admin/login/', {'username': self.alice.phone, 'password': PASSWORD})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_guest_text_is_escaped(self):
        self.own.name = '<script>alert(1)</script>'; self.own.save()
        self.login()
        r = self.client.get('/admin/')
        self.assertContains(r, '&lt;script&gt;')
        self.assertNotContains(r, '<script>alert(1)</script>')

    def test_persistent_login_request_budget(self):
        for _ in range(30):
            self.client.post('/admin/login/', {'username': self.alice.phone, 'password': 'wrong'})
        r = self.client.post('/admin/login/', {'username': self.alice.phone, 'password': PASSWORD})
        self.assertEqual(r.status_code, 429)
        self.assertGreater(int(r['Retry-After']), 0)
        self.assertTrue(AuthRateLimit.objects.exists())

    def test_health_and_phone_normalization(self):
        self.assertJSONEqual(self.client.get('/api/health/').content, {'status': 'ok'})
        self.assertEqual(normalize_phone('+55 (24) 98888-0001'), self.alice.phone)
        self.assertEqual(normalize_phone('5524988880001'), self.alice.phone)

    @override_settings(TRUST_PROXY=False)
    def test_forwarded_ip_is_ignored_without_trusted_proxy(self):
        self.client.post('/admin/login/', {'username': self.alice.phone, 'password': 'wrong'}, HTTP_X_FORWARDED_FOR='192.0.2.1')
        self.client.post('/admin/login/', {'username': self.alice.phone, 'password': 'wrong'}, HTTP_X_FORWARDED_FOR='192.0.2.2')
        self.assertEqual(AuthRateLimit.objects.count(), 1)
        self.assertEqual(AuthRateLimit.objects.get().count, 2)

    @override_settings(TRUST_PROXY=True)
    def test_trusted_proxy_keeps_separate_visitor_budgets(self):
        self.client.post('/admin/login/', {'username': self.alice.phone, 'password': 'wrong'}, HTTP_X_FORWARDED_FOR='192.0.2.1')
        self.client.post('/admin/login/', {'username': self.alice.phone, 'password': 'wrong'}, HTTP_X_FORWARDED_FOR='192.0.2.2')
        self.assertEqual(AuthRateLimit.objects.count(), 2)

    def test_organizer_can_add_guest_without_selecting_owner(self):
        self.login(self.organizer)
        response = self.client.post(reverse('admin:guests_guest_add'), {'name': 'Convidado sem seleção', 'attendance': 'pending', 'family': '', '_save': 'Salvar'})
        self.assertRedirects(response, '/admin/')
        self.assertEqual(Guest.objects.get(name='Convidado sem seleção').family.responsible, self.organizer)

    def test_empty_owner_on_edit_keeps_existing_list(self):
        self.login(self.organizer)
        response = self.client.post(reverse('admin:guests_guest_change', args=[self.foreign.pk]), {'name': self.foreign.name, 'attendance': 'yes', 'family': '', '_save': 'Salvar'})
        self.assertRedirects(response, '/admin/')
        self.foreign.refresh_from_db()
        self.assertEqual(self.foreign.family.responsible, self.bia)


class AdminBootstrapTests(TestCase):
    def test_bootstrap_creates_admin_even_when_common_users_exist_and_is_idempotent(self):
        import os
        from unittest.mock import patch
        from ensure_superuser import main
        User.objects.create_user('24988881111', PASSWORD, first_name='Conta comum')
        with patch.dict(os.environ, {'DJANGO_ADMIN_PHONE': '+5524999999999', 'DJANGO_ADMIN_PASSWORD': 'Initial!AdminPass', 'DJANGO_ADMIN_NAME': 'Organização'}):
            main()
        admin = User.objects.get(phone='+5524999999999')
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password('Initial!AdminPass'))
        with patch.dict(os.environ, {'DJANGO_ADMIN_PASSWORD': 'DoNotReset!Password'}):
            main()
        admin.refresh_from_db()
        self.assertTrue(admin.check_password('Initial!AdminPass'))
        self.assertEqual(User.objects.filter(is_superuser=True).count(), 1)

    @override_settings(DEBUG=False)
    def test_production_requires_explicit_credentials_and_never_promotes_common_users(self):
        import os
        from unittest.mock import patch
        from ensure_superuser import main
        with patch.dict(os.environ, {'DJANGO_ADMIN_PHONE': '', 'DJANGO_ADMIN_PASSWORD': ''}):
            with self.assertRaises(RuntimeError):
                main()
        user = User.objects.create_user('24999999999', PASSWORD, first_name='Conta comum')
        with patch.dict(os.environ, {'DJANGO_ADMIN_PHONE': user.phone, 'DJANGO_ADMIN_PASSWORD': 'Something!Strong'}):
            with self.assertRaises(RuntimeError):
                main()
        user.refresh_from_db()
        self.assertFalse(user.is_superuser)


class FamilyTests(TestCase):
    def setUp(self):
        self.responsible = User.objects.create_user('24988882222', PASSWORD, first_name='Responsável da família')
        self.other = User.objects.create_user('24988883333', PASSWORD, first_name='Outra família')
        self.client.force_login(self.responsible)

    def test_account_automatically_creates_one_family(self):
        self.assertEqual(Family.objects.filter(responsible=self.responsible).count(), 1)
        self.responsible.save()
        self.assertEqual(Family.objects.filter(responsible=self.responsible).count(), 1)

    def test_family_inline_creates_members_without_accounts_or_phones(self):
        organizer = User.objects.create_superuser('24988884444', PASSWORD, first_name='Organização')
        self.client.force_login(organizer)
        accounts_before = User.objects.count()
        r = self.client.post(reverse('admin:guests_family_change', args=[self.responsible.family.pk]), {
            'name': 'Família Silva', '_save': 'Salvar',
            'guests-TOTAL_FORMS': '2', 'guests-INITIAL_FORMS': '0', 'guests-MIN_NUM_FORMS': '0', 'guests-MAX_NUM_FORMS': '1000',
            'guests-0-name': 'Primeiro familiar', 'guests-0-attendance': 'yes',
            'guests-1-name': 'Segundo familiar', 'guests-1-attendance': 'pending',
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(User.objects.count(), accounts_before)
        self.assertEqual(self.responsible.family.guests.count(), 2)
        self.assertTrue(all(g.phone == '' for g in self.responsible.family.guests.all()))
        self.assertIsNotNone(self.responsible.family.guests.get(name='Primeiro familiar').attendance_updated_at)

    def test_family_admin_never_exposes_other_families(self):
        other_guest = Guest.objects.create(family=self.other.family, name='Nome privado da outra família')
        r = self.client.get(reverse('admin:guests_family_changelist'))
        self.assertContains(r, 'Responsável da família')
        self.assertNotContains(r, 'Outra família')
        r = self.client.get(reverse('admin:guests_family_change', args=[self.other.family.pk]), follow=True)
        self.assertNotContains(r, other_guest.name)
        self.assertEqual(self.client.get(reverse('admin:guests_family_add')).status_code, 403)

    def test_responsible_cannot_bypass_guest_restrictions_via_family_inline(self):
        guest = Guest.objects.create(family=self.responsible.family, name='Nome mantido')
        r = self.client.post(reverse('admin:guests_family_change', args=[self.responsible.family.pk]), {
            'name': 'Família alterada', '_save': 'Salvar',
            'guests-TOTAL_FORMS': '2', 'guests-INITIAL_FORMS': '1', 'guests-MIN_NUM_FORMS': '0', 'guests-MAX_NUM_FORMS': '1000',
            'guests-0-id': str(guest.pk), 'guests-0-name': 'Nome alterado', 'guests-0-attendance': 'no', 'guests-0-DELETE': 'on',
            'guests-1-name': 'Inclusão indevida', 'guests-1-attendance': 'yes',
        })
        self.assertEqual(r.status_code, 403)
        guest.refresh_from_db()
        self.assertEqual(guest.name, 'Nome mantido')
        self.assertEqual(guest.attendance, Attendance.PENDING)
        self.assertEqual(self.responsible.family.guests.count(), 1)
        response = self.client.get(reverse('admin:guests_family_change', args=[self.responsible.family.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nome mantido')
        self.assertNotContains(response, 'name="guests-0-name"')


class AccountActivationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('24988885555', password=None, first_name='Tia Márcia Silva', attendance='yes')
        self.guest = Guest.objects.create(family=self.user.family, name='Familiar existente', attendance='no')
        self.payload = {'first_name': '  MARCIA  SILVA ', 'phone': '(24) 98888-5555', 'password1': PASSWORD, 'password2': PASSWORD}

    def test_imported_account_can_activate_preserving_family_and_responses(self):
        family_id = self.user.family.pk
        r = self.client.post('/cadastro/', self.payload)
        self.assertRedirects(r, '/admin/')
        self.user.refresh_from_db(); self.guest.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))
        self.assertEqual(self.user.first_name, 'Tia Márcia Silva')
        self.assertEqual(self.user.attendance, 'yes')
        self.assertEqual(self.user.family.pk, family_id)
        self.assertEqual(self.guest.attendance, 'no')
        self.assertEqual(User.objects.count(), 1)

    def test_unknown_phone_or_wrong_name_is_rejected_without_creating_account(self):
        for values in ({'phone': '24988886666'}, {'first_name': 'Outra pessoa'}, {'first_name': 'Márcia'}):
            r = self.client.post('/cadastro/', {**self.payload, **values})
            self.assertContains(r, 'Pessoa não cadastrada')
            self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(User.objects.count(), 1)
        self.user.refresh_from_db()
        self.assertFalse(self.user.has_usable_password())

    def test_password_confirmation_and_validation_are_enforced(self):
        for values in ({'password2': 'Different!Password'}, {'password1': '12345678', 'password2': '12345678'}):
            r = self.client.post('/cadastro/', {**self.payload, **values})
            self.assertIn('password2', r.context['form'].errors)
        self.user.refresh_from_db()
        self.assertFalse(self.user.has_usable_password())

    def test_privileged_and_inactive_accounts_cannot_reset_here(self):
        for flags in ({'is_superuser': True, 'is_staff': True}, {'is_active': False}):
            User.objects.filter(pk=self.user.pk).update(is_superuser=False, is_staff=False, is_active=True)
            User.objects.filter(pk=self.user.pk).update(**flags)
            r = self.client.post('/cadastro/', self.payload)
            self.assertContains(r, 'Pessoa não cadastrada')
            self.assertNotIn('_auth_user_id', self.client.session)
        self.user.refresh_from_db()
        self.assertFalse(self.user.has_usable_password())
