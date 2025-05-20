from django.shortcuts import redirect
from django.urls import reverse

class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.login_url = reverse('login')
        self.open_urls = [reverse('login'), reverse('logout'), reverse('about')]

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        path = request.path_info
        
        if not request.user.is_authenticated and path not in self.open_urls:
            return redirect(f"{self.login_url}?next={path}")