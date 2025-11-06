from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
import sys


print("[LoginRequiredMiddleware] module imported", file=sys.stderr)


class LoginRequiredMiddleware(MiddlewareMixin):
    """Require login for all pages except a whitelist.

    Whitelist includes:
    - homepage (named 'home')
    - login/signup/signup_success pages under accounts
    - static and media files
    - admin URLs (so admin login works)
    """

    def process_request(self, request):
        # Debug: log request and authentication state
        try:
            user = getattr(request, 'user', None)
            is_auth = bool(user and user.is_authenticated)
        except Exception:
            user = None
            is_auth = False
        print(f"[LoginRequiredMiddleware] request path={request.path_info} authenticated={is_auth}", file=sys.stderr)

        # If the user is already authenticated, allow the request.
        if is_auth:
            return None

        path = request.path_info or request.path

        # Normalize static/media prefixes into form '/prefix/' (don't allow bare '/')
        def _norm_prefix(url_value, default):
            if not url_value:
                return default
            s = str(url_value)
            # ensure leading slash
            if not s.startswith('/'):
                s = '/' + s
            # ensure trailing slash
            if not s.endswith('/'):
                s = s + '/'
            # avoid root-only '/'
            if s == '/':
                return default
            return s

        static_url = _norm_prefix(getattr(settings, 'STATIC_URL', ''), '/static/')
        media_url = _norm_prefix(getattr(settings, 'MEDIA_URL', ''), '')

        # Build a small whitelist of allowed paths that don't require login.
        allowed_paths = set()
        try:
            allowed_paths.add(reverse('home'))
        except Exception:
            allowed_paths.add('/')

        # Allow account auth flows (login, signup, signup_success) so users can sign in.
        try:
            allowed_paths.add(reverse('accounts:login'))
        except Exception:
            allowed_paths.add('/accounts/login/')
        try:
            allowed_paths.add(reverse('accounts:signup'))
        except Exception:
            allowed_paths.add('/accounts/signup/')
        try:
            allowed_paths.add(reverse('accounts:signup_success'))
        except Exception:
            allowed_paths.add('/accounts/signup/success/')

        # Allow the logout endpoint so users can sign out even if not authenticated
        # (logout view handles logout safely).
        try:
            allowed_paths.add(reverse('accounts:logout'))
        except Exception:
            allowed_paths.add('/accounts/logout/')

        # Admin URLs (login) should be reachable
        allowed_prefixes = [p for p in (static_url, media_url, '/admin/') if p]
        print(f"[LoginRequiredMiddleware] allowed_prefixes={allowed_prefixes}", file=sys.stderr)

        # If the request path is explicitly allowed, let it through
        if path in allowed_paths:
            print(f"[LoginRequiredMiddleware] path in allowed_paths: {path}", file=sys.stderr)
            return None

        # If the request path starts with any allowed prefix, let it through
        for pfx in allowed_prefixes:
            if pfx and path.startswith(pfx):
                print(f"[LoginRequiredMiddleware] path startswith allowed prefix {pfx}: {path}", file=sys.stderr)
                return None

        # Otherwise redirect to login with next parameter set to current path
        try:
            login_url = reverse('accounts:login')
        except Exception:
            login_url = '/accounts/login/'

        redirect_url = f"{login_url}?next={request.get_full_path()}"
        print(f"[LoginRequiredMiddleware] redirecting to: {redirect_url}", file=sys.stderr)
        return redirect(redirect_url)
