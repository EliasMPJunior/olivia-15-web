#!/usr/bin/env python
"""python redefinir_senhas.py [--dry-run]"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

if __name__ == '__main__':
    import django
    from django.core.management import call_command
    django.setup()
    call_command('redefinir_senhas', *sys.argv[1:])
