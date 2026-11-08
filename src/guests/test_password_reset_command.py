from io import StringIO
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from .models import Guest, User


class PasswordResetCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('24988881234', 'Original!Secret', first_name='Responsável', attendance='yes')
        self.guest = Guest.objects.create(family=self.user.family, name='Familiar', attendance='no')
        self.admin = User.objects.create_superuser('24988885678', 'Admin!Secret', first_name='Admin')
        self.staff = User.objects.create_user('24988889012', 'Staff!Secret', first_name='Staff', is_staff=True)
        self.inactive = User.objects.create_user('24988883456', None, first_name='Inativo', is_active=False)

    def test_updates_common_accounts_and_preserves_all_admins_and_family_data(self):
        admin_hash, staff_hash = self.admin.password, self.staff.password
        out = StringIO(); call_command('redefinir_senhas', stdout=out)
        self.user.refresh_from_db(); self.admin.refresh_from_db(); self.staff.refresh_from_db(); self.inactive.refresh_from_db(); self.guest.refresh_from_db()
        self.assertTrue(self.user.check_password('20261234'))
        self.assertTrue(self.inactive.check_password('20263456'))
        self.assertFalse(self.inactive.is_active)
        self.assertNotEqual(self.user.password, '20261234')
        self.assertEqual(self.admin.password, admin_hash)
        self.assertEqual(self.staff.password, staff_hash)
        self.assertEqual(self.user.attendance, 'yes')
        self.assertEqual(self.guest.attendance, 'no')
        self.assertNotIn('20261234', out.getvalue())

    def test_dry_run_writes_nothing(self):
        original = self.user.password
        call_command('redefinir_senhas', '--dry-run', stdout=StringIO())
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, original)
        self.assertTrue(self.user.check_password('Original!Secret'))

    def test_second_run_keeps_existing_hashes(self):
        call_command('redefinir_senhas', stdout=StringIO())
        self.user.refresh_from_db(); first = self.user.password
        call_command('redefinir_senhas', stdout=StringIO())
        self.user.refresh_from_db()
        self.assertEqual(first, self.user.password)

    def test_invalid_phone_rolls_back_previous_updates(self):
        User.objects.filter(pk=self.inactive.pk).update(phone='invalid')
        original = self.user.password
        with self.assertRaises(CommandError):
            call_command('redefinir_senhas', stdout=StringIO())
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, original)

    @override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher', 'django.contrib.auth.hashers.PBKDF2PasswordHasher'])
    def test_dry_run_does_not_upgrade_password_hashes(self):
        from django.contrib.auth.hashers import make_password
        original = make_password('20261234', hasher='pbkdf2_sha256')
        User.objects.filter(pk=self.user.pk).update(password=original)
        call_command('redefinir_senhas', '--dry-run', stdout=StringIO())
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, original)
