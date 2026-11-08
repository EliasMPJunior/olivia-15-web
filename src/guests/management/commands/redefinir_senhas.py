from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import check_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from guests.models import User
from guests.passwords import initial_responsible_password


class Command(BaseCommand):
    help = 'Aplica 2026 + os últimos quatro dígitos do telefone às contas que não são staff nem superusuários.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Confere as contas sem gravar as senhas.')

    def handle(self, *args, **options):
        changed = unchanged = 0
        with transaction.atomic():
            users = User.objects.select_for_update().filter(is_superuser=False, is_staff=False).order_by('pk')
            for user in users.iterator():
                try:
                    password = initial_responsible_password(user.phone)
                except ValidationError as exc:
                    raise CommandError(f'Conta de ID {user.pk} com telefone inválido. Nenhuma senha foi alterada.') from exc
                if check_password(password, user.password):
                    unchanged += 1
                    continue
                if not options['dry_run']:
                    user.set_password(password)
                    # Check privileges again at write time; never reset an admin.
                    changed += User.objects.filter(pk=user.pk, is_superuser=False, is_staff=False).update(password=user.password)
                else:
                    changed += 1
        if options['dry_run']:
            self.stdout.write(f'Simulação: {changed} senha(s) seriam alteradas; {unchanged} já seguem o padrão. Nenhuma alteração gravada.')
        else:
            self.stdout.write(self.style.SUCCESS(f'{changed} senha(s) atualizadas; {unchanged} já seguiam o padrão.'))
        self.stdout.write('Contas staff e superusuários foram preservadas.')
