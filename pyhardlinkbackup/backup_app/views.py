from django.http import HttpResponseRedirect


def redirect_to_admin(request):
    return HttpResponseRedirect("/admin")
