#!/usr/bin/env python
"""python remover_prefixo_55.py [--dry-run]"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

if __name__ == '__main__':
    import django
    from django.core.management import call_command
    django.setup()
    call_command('remover_prefixo_55', *sys.argv[1:])
