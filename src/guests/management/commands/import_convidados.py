"""Import the principal/guests JSON into family accounts without resetting data."""
import copy
import json
import unicodedata
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from guests.models import Family, Guest, User, normalize_phone, phone_variants


FIELDS = {'tratamento', 'nome', 'sobrenome', 'telefone'}


def text(value):
    return ' '.join((value or '').split())


def identity(value):
    return unicodedata.normalize('NFKC', text(value)).casefold()


def validate_person(person):
    if not isinstance(person, dict) or set(person) - FIELDS:
        raise ValueError('Pessoa deve ser um objeto com tratamento, nome, sobrenome e telefone.')
    if any(value is not None and not isinstance(value, str) for value in person.values()):
        raise ValueError('Os dados da pessoa devem ser texto ou null.')
    name = ' '.join(filter(None, (text(person.get(field)) for field in ('tratamento', 'nome', 'sobrenome'))))
    if not name:
        raise ValueError('Pessoa sem nome ou tratamento identificável.')
    if len(name) > 150:
        raise ValueError(f'Nome maior que 150 caracteres: {name}.')
    phone = text(person.get('telefone'))
    if len(phone) > 32:
        raise ValueError(f'Telefone maior que 32 caracteres para {name}.')
    return name, phone


class Command(BaseCommand):
    help = 'Importa principais, famílias e convidados de data/convidados.json sem duplicar registros.'

    def add_arguments(self, parser):
        parser.add_argument('arquivo', nargs='?', default=str(settings.BASE_DIR / 'data' / 'convidados.json'))
        parser.add_argument('--dry-run', action='store_true', help='Simula a importação e desfaz todas as alterações no banco.')
        parser.add_argument('--strict', action='store_true', help='Desfaz toda a importação se houver qualquer grupo inválido.')
        parser.add_argument('--report', type=Path, help='Grava um relatório JSON de totais, avisos e grupos pendentes.')

    def handle(self, *args, **options):
        source = Path(options['arquivo'])
        try:
            data = json.loads(source.read_text(encoding='utf-8-sig'))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CommandError(f'Não foi possível ler {source}: {exc}') from exc
        if not isinstance(data, list):
            raise CommandError('O JSON deve conter uma lista de grupos.')
        if options['report'] and options['report'].resolve() == source.resolve():
            raise CommandError('O relatório não pode substituir a lista original.')
        report = {
            'arquivo': str(source), 'simulacao': options['dry_run'],
            'grupos': len(data), 'responsaveis_criados': 0, 'responsaveis_existentes': 0,
            'familias_criadas': 0, 'convidados_criados': 0, 'convidados_existentes': 0,
            'telefones_preenchidos': 0, 'pendencias': [], 'avisos': [],
        }
        with transaction.atomic():
            for index, group in enumerate(data, start=1):
                snapshot = copy.deepcopy(report)
                try:
                    # One invalid group cannot leave an incomplete family behind.
                    with transaction.atomic():
                        self.import_group(group, index, report)
                except (ValueError, ValidationError) as exc:
                    report = snapshot
                    reason = '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
                    issue = {'grupo': index, 'motivo': reason}
                    report['pendencias'].append(issue)
                    self.stderr.write(f'Grupo {index} não importado: {reason}')
                    if options['strict']:
                        raise CommandError(f'Importação desfeita: grupo {index}: {reason}') from exc
            if options['dry_run']:
                transaction.set_rollback(True)
        if options['report']:
            destination = options['report']
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        for warning in report['avisos']:
            self.stderr.write(f'Aviso: {warning}')
        label = 'Simulação concluída; banco preservado.' if options['dry_run'] else 'Importação concluída.'
        self.stdout.write(self.style.SUCCESS(label))
        self.stdout.write(
            f"Responsáveis: {report['responsaveis_criados']} novos, {report['responsaveis_existentes']} existentes. "
            f"Convidados: {report['convidados_criados']} novos, {report['convidados_existentes']} existentes. "
            f"Grupos pendentes: {len(report['pendencias'])}."
        )

    def import_group(self, group, index, report):
        if not isinstance(group, dict) or set(group) != {'principal', 'guests'} or not isinstance(group['guests'], list):
            raise ValueError('Grupo deve conter principal e uma lista guests.')
        principal_name, raw_phone = validate_person(group['principal'])
        if not raw_phone:
            raise ValueError(f'Principal sem telefone: {principal_name}. Preencha o JSON e execute novamente.')
        phone = normalize_phone(raw_phone)
        people = [validate_person(person) for person in group['guests']]
        matches = list(User.objects.filter(phone__in=phone_variants(phone))[:2])
        if len(matches) > 1:
            raise ValueError('Há contas duplicadas para o telefone do principal; revise os cadastros antes de importar.')
        user = matches[0] if matches else None
        if user is None:
            # No shared/default password and no elevation of administrative access.
            user = User.objects.create_user(phone=phone, first_name=principal_name, password=None)
            report['responsaveis_criados'] += 1
            report['familias_criadas'] += 1  # Created by the User post_save signal.
        else:
            report['responsaveis_existentes'] += 1
            if identity(user.first_name) != identity(principal_name):
                report['avisos'].append(f'Grupo {index}: telefone já cadastrado como {user.first_name}; nome existente preservado ({principal_name} no arquivo).')
        family, created = Family.objects.get_or_create(responsible=user)
        if created:
            report['familias_criadas'] += 1
        for guest_name, guest_phone in people:
            if identity(guest_name) == identity(principal_name):
                report['avisos'].append(f'Grupo {index}: principal repetido em guests ({guest_name}); ignorado.')
                continue
            existing = [guest for guest in family.guests.all() if identity(guest.name) == identity(guest_name)]
            if len(existing) > 1:
                report['avisos'].append(f'Grupo {index}: já há vários convidados chamados {guest_name}; registros preservados para revisão.')
                report['convidados_existentes'] += 1
                continue
            if existing:
                guest = existing[0]
                report['convidados_existentes'] += 1
                if guest_phone and not guest.phone:
                    guest.phone = guest_phone
                    guest.save(update_fields=['phone'])
                    report['telefones_preenchidos'] += 1
                elif guest_phone and guest.phone != guest_phone:
                    report['avisos'].append(f'Grupo {index}: telefone de {guest_name} já preenchido; valor existente preservado.')
            else:
                Guest.objects.create(family=family, name=guest_name, phone=guest_phone)
                report['convidados_criados'] += 1
