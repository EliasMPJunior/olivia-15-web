from django.apps import AppConfig

class GuestsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'guests'
    verbose_name = 'Minha lista'

    def ready(self):
        from . import signals  # noqa: F401
