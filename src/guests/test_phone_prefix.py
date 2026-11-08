from io import StringIO
from django.core.management import call_command, CommandError
from django.test import TestCase
from .models import Guest, User, normalize_phone


class PhonePrefixTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('24988881234', 'Original!Password', first_name='Responsável', attendance='yes')
        self.admin = User.objects.create_superuser('24988885678', 'Admin!Password', first_name='Admin')
        # Simulate records stored before the new local-number convention.
        User.objects.filter(pk=self.user.pk).update(phone='+5524988881234')
        User.objects.filter(pk=self.admin.pk).update(phone='+5524988885678')
        self.guest = Guest.objects.create(family=self.user.family, name='Convidado', phone='+55 24 98888-7890', attendance='no')
        self.international = Guest.objects.create(family=self.user.family, name='Internacional', phone='+1 (774) 487-9153')

    def test_removes_prefix_for_accounts_including_admins_and_guests_only(self):
        original_hash = self.user.password
        call_command('remover_prefixo_55', stdout=StringIO())
        self.user.refresh_from_db(); self.admin.refresh_from_db(); self.guest.refresh_from_db(); self.international.refresh_from_db()
        self.assertEqual(self.user.phone, '24988881234')
        self.assertEqual(self.admin.phone, '24988885678')
        self.assertEqual(self.guest.phone, '24 98888-7890')
        self.assertEqual(self.international.phone, '+1 (774) 487-9153')
        self.assertEqual(self.user.password, original_hash)
        self.assertEqual(self.user.attendance, 'yes')
        self.assertEqual(self.guest.attendance, 'no')
        self.assertEqual(self.guest.family.responsible_id, self.user.pk)
        call_command('remover_prefixo_55', stdout=StringIO())
        self.user.first_name = 'Nome alterado'; self.user.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, '24988881234')

    def test_dry_run_leaves_all_phones_untouched(self):
        call_command('remover_prefixo_55', '--dry-run', stdout=StringIO())
        self.user.refresh_from_db(); self.guest.refresh_from_db()
        self.assertEqual(self.user.phone, '+5524988881234')
        self.assertEqual(self.guest.phone, '+55 24 98888-7890')

    def test_duplicate_result_aborts_without_modifying_any_record(self):
        User.objects.create_user('24988881234', None, first_name='Outro cadastro')
        with self.assertRaises(CommandError):
            call_command('remover_prefixo_55', stdout=StringIO())
        self.user.refresh_from_db(); self.guest.refresh_from_db()
        self.assertEqual(self.user.phone, '+5524988881234')
        self.assertEqual(self.guest.phone, '+55 24 98888-7890')

    def test_login_accepts_both_formats_before_and_after_conversion(self):
        for converted in (False, True):
            if converted:
                call_command('remover_prefixo_55', stdout=StringIO())
            for phone in ('(24) 98888-1234', '+55 (24) 98888-1234'):
                self.client.logout()
                response = self.client.post('/admin/login/', {'username': phone, 'password': 'Original!Password', 'next': '/admin/'})
                self.assertRedirects(response, '/admin/')

    def test_existing_legacy_phone_cannot_be_registered_twice_in_admin(self):
        self.client.force_login(self.admin)
        response = self.client.post('/admin/guests/user/add/', {'first_name': 'Duplicado', 'phone': '(24) 98888-1234', '_save': 'Salvar'})
        self.assertIn('phone', response.context['adminform'].form.errors)
        self.assertEqual(User.objects.count(), 2)

    def test_normalization_drops_only_brazilian_country_code(self):
        self.assertEqual(normalize_phone('+55 (24) 98888-1234'), '24988881234')
        self.assertEqual(normalize_phone('5524988881234'), '24988881234')
        self.assertEqual(normalize_phone('55988881234'), '55988881234')
        self.assertEqual(normalize_phone('+1 (774) 487-9153'), '+17744879153')
