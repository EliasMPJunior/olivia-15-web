import copy
import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command, CommandError
from django.test import TestCase
from .models import Family, Guest, User


class ImportGuestsTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name) / 'convidados.json'
        self.report = Path(self.directory.name) / 'report.json'
        self.data = [{
            'principal': {'tratamento': 'Tia', 'nome': 'Ana', 'sobrenome': 'Silva', 'telefone': '(24) 98888-1111'},
            'guests': [
                {'tratamento': 'Tio', 'nome': 'Paulo', 'sobrenome': 'Silva', 'telefone': '24988882222'},
                {'tratamento': None, 'nome': 'Maria Clara', 'sobrenome': None, 'telefone': None},
            ],
        }]

    def run_import(self, *flags, data=None):
        self.source.write_text(json.dumps(self.data if data is None else data), encoding='utf-8')
        call_command('import_convidados', str(self.source), *flags, '--report', str(self.report), stdout=StringIO(), stderr=StringIO())
        return json.loads(self.report.read_text())

    def test_import_maps_principal_to_account_and_members_to_family(self):
        report = self.run_import()
        responsible = User.objects.get(phone='24988881111')
        self.assertEqual(responsible.first_name, 'Tia Ana Silva')
        self.assertFalse(responsible.has_usable_password())
        self.assertFalse(responsible.is_staff)
        self.assertFalse(responsible.is_superuser)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Family.objects.count(), 1)
        self.assertEqual(responsible.family.guests.count(), 2)
        self.assertEqual(Guest.objects.get(name='Tio Paulo Silva').phone, '24988882222')
        self.assertEqual(Guest.objects.get(name='Maria Clara').phone, '')
        self.assertEqual(report['responsaveis_criados'], 1)

    def test_rerun_deduplicates_and_preserves_password_and_responses(self):
        self.run_import()
        user = User.objects.get()
        user.set_password('Personal!Password123'); user.attendance = 'yes'; user.save()
        guest = Guest.objects.get(name='Tio Paulo Silva'); guest.attendance = 'no'; guest.save()
        self.data[0]['principal']['telefone'] = '+55 24 98888-1111'
        self.data[0]['guests'][0]['nome'] = '  PAULO  '
        report = self.run_import()
        user.refresh_from_db(); guest.refresh_from_db()
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Guest.objects.count(), 2)
        self.assertEqual(report['responsaveis_existentes'], 1)
        self.assertEqual(report['convidados_existentes'], 2)
        self.assertTrue(user.check_password('Personal!Password123'))
        self.assertEqual(user.attendance, 'yes')
        self.assertEqual(guest.attendance, 'no')

    def test_dry_run_changes_nothing(self):
        report = self.run_import('--dry-run')
        self.assertTrue(report['simulacao'])
        self.assertEqual(report['convidados_criados'], 2)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Family.objects.count(), 0)
        self.assertEqual(Guest.objects.count(), 0)

    def test_invalid_group_is_skipped_as_a_whole_and_reported(self):
        invalid = copy.deepcopy(self.data[0]); invalid['principal']['telefone'] = None
        report = self.run_import(data=[invalid, self.data[0]])
        self.assertEqual(len(report['pendencias']), 1)
        self.assertEqual(report['pendencias'][0]['grupo'], 1)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Guest.objects.count(), 2)
        invalid = copy.deepcopy(self.data[0]); invalid['guests'].append({'nome': None})
        report = self.run_import(data=[invalid])
        self.assertEqual(len(report['pendencias']), 1)
        self.assertEqual(User.objects.count(), 1)

    def test_strict_mode_rolls_back_all_groups(self):
        invalid = copy.deepcopy(self.data[0]); invalid['principal']['telefone'] = '123'
        with self.assertRaises(CommandError):
            self.run_import('--strict', data=[self.data[0], invalid])
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Guest.objects.count(), 0)

    def test_same_guest_name_in_different_families_is_not_merged(self):
        other = copy.deepcopy(self.data[0]); other['principal']['nome'] = 'Beatriz'; other['principal']['telefone'] = '24988883333'
        self.run_import(data=[self.data[0], other])
        self.assertEqual(Family.objects.count(), 2)
        self.assertEqual(Guest.objects.filter(name='Maria Clara').count(), 2)

    def test_only_missing_guest_phone_is_filled(self):
        self.run_import()
        guest = Guest.objects.get(name='Tio Paulo Silva'); guest.phone = ''; guest.save()
        report = self.run_import()
        self.assertEqual(report['telefones_preenchidos'], 1)
        guest.refresh_from_db(); self.assertEqual(guest.phone, '24988882222')
        self.data[0]['guests'][0]['telefone'] = '24999990000'
        report = self.run_import()
        guest.refresh_from_db(); self.assertEqual(guest.phone, '24988882222')
        self.assertTrue(report['avisos'])

    def test_report_cannot_overwrite_source(self):
        self.source.write_text(json.dumps(self.data))
        with self.assertRaises(CommandError):
            call_command('import_convidados', str(self.source), '--report', str(self.source), stdout=StringIO())
        self.assertEqual(User.objects.count(), 0)
