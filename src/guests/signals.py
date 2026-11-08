from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Family


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_family_for_responsible(sender, instance, created, raw=False, using=None, **kwargs):
    if created and not raw:
        Family.objects.using(using).get_or_create(responsible=instance)
