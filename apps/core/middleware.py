from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """Send generated-password users to the change form before anything else."""

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            state = getattr(user, 'password_state', None)
            if state and state.must_change_password:
                allowed_paths = {
                    reverse('login'),
                    reverse('logout'),
                    reverse('password_change'),
                }
                if request.path not in allowed_paths and not request.path.startswith('/static/'):
                    return redirect('password_change')
        return self.get_response(request)

    def __init__(self, get_response):
        self.get_response = get_response
