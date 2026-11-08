from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.db import transaction
from guests.models import Guest, User, normalize_phone


class Command(BaseCommand):
    help = 'Remove +55 do início dos telefones de todas as contas e convidados, incluindo administradores.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Confere alterações e colisões sem gravar no banco.')

    def handle(self, *args, **options):
        with transaction.atomic():
            users = list(User.objects.select_for_update().order_by('pk').values_list('pk', 'phone'))
            changes = []
            seen = {}
            for pk, phone in users:
                target = phone[3:].lstrip() if phone.startswith('+55') else phone
                if phone.startswith('+55'):
                    try:
                        target = normalize_phone(target)
                    except ValidationError as exc:
                        raise CommandError(f'Telefone inválido na conta {pk}; nenhuma alteração gravada.') from exc
                    changes.append((pk, target))
                if target in seen:
                    raise CommandError(f'Contas {seen[target]} e {pk} ficariam com o mesmo telefone. Nenhuma alteração gravada.')
                seen[target] = pk
            guests = list(Guest.objects.select_for_update().filter(phone__startswith='+55').values_list('pk', 'phone'))
            if not options['dry_run']:
                # Bypass save hooks: change only the phone, never password/profile.
                for pk, phone in changes:
                    User.objects.filter(pk=pk).update(phone=phone)
                for pk, phone in guests:
                    Guest.objects.filter(pk=pk).update(phone=phone[3:].lstrip())
        label = 'Simulação; nenhuma alteração gravada' if options['dry_run'] else 'Prefixo removido'
        self.stdout.write(self.style.SUCCESS(f'{label}: {len(changes)} conta(s), {len(guests)} convidado(s).'))
