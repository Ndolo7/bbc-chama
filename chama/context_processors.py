from .models import Member


def sidebar_members(request):
    if request.user.is_authenticated:
        return {'sidebar_members': Member.objects.filter(is_active=True)}
    return {'sidebar_members': []}
