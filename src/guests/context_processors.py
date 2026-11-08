from django.conf import settings

def invitation(request):
    return {'invitation_url': settings.INVITATION_URL}
