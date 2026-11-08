import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch
from django.test import SimpleTestCase
from ensure_secret_key import main


class ProductionSecretTests(SimpleTestCase):
    def test_generated_key_persists_across_restarts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'secret'
            with patch.dict(os.environ, {'DJANGO_DEBUG': '0', 'DJANGO_SECRET_KEY': '', 'DJANGO_SECRET_KEY_FILE': str(path)}):
                main()
                first = path.read_text()
                main()
                self.assertEqual(path.read_text(), first)
                self.assertGreater(len(first.strip()), 50)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_explicit_environment_key_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'secret'
            with patch.dict(os.environ, {'DJANGO_DEBUG': '0', 'DJANGO_SECRET_KEY': 'explicit-test-key', 'DJANGO_SECRET_KEY_FILE': str(path)}):
                main()
                self.assertFalse(path.exists())

    def test_empty_key_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'secret'; path.touch()
            with patch.dict(os.environ, {'DJANGO_DEBUG': '0', 'DJANGO_SECRET_KEY': '', 'DJANGO_SECRET_KEY_FILE': str(path)}):
                with self.assertRaises(RuntimeError):
                    main()
