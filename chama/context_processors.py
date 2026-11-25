from django.conf import settings

from .demo import is_demo_user
from .models import Member


def sidebar_members(request):
    if request.user.is_authenticated:
        return {'sidebar_members': Member.objects.filter(is_active=True)}
    return {'sidebar_members': []}


def demo(request):
    return {
        'demo_enabled': settings.DEMO_ENABLED,
        'is_demo': is_demo_user(getattr(request, 'user', None)),
        'demo_reset_hours': settings.DEMO_RESET_HOURS,
    }
