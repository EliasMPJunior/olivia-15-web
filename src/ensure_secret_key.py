"""Persist a unique production key in the data volume before Django starts."""
import os
import secrets
from pathlib import Path


def main():
    if os.getenv('DJANGO_DEBUG', '0') == '1' or os.getenv('DJANGO_SECRET_KEY'):
        return
    path = os.getenv('DJANGO_SECRET_KEY_FILE')
    if not path:
        raise RuntimeError('Defina DJANGO_SECRET_KEY ou DJANGO_SECRET_KEY_FILE em produção.')
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass  # Keep existing sessions valid across container rebuilds/restarts.
    else:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(secrets.token_urlsafe(64) + '\n')
    if not destination.read_text(encoding='utf-8').strip():
        raise RuntimeError('O arquivo da chave secreta está vazio; configure DJANGO_SECRET_KEY.')


if __name__ == '__main__':
    main()
