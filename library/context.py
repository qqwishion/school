from django.conf import settings

def site_context(request):
    return {'demo_mode': settings.DEMO_MODE}
