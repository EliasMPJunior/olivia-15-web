#!/usr/bin/env python
"""Standalone entrypoint: python import_convidados.py [arquivo] [--dry-run]."""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

if __name__ == '__main__':
    import django
    from django.core.management import call_command
    django.setup()
    call_command('import_convidados', *sys.argv[1:])
