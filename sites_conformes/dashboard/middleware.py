from django.conf import settings
from wagtail_2fa.middleware import VerifyUserMiddleware


class VerifyUserStaticFilesMiddleware(VerifyUserMiddleware):
    """
    Extends VerifyUserMiddleware to skip 2FA verification for static and media file requests.
    Without this, when WAGTAIL_2FA_REQUIRED=True, static files served to an authenticated
    user without a configured 2FA device are redirected to the setup page, causing MIME errors.

    Also allows the ProConnect (OIDC) logout callback through unverified. When
    PROCONNECT_ACTIVATED=True, "Sign out" on the 2FA code-entry screen redirects the
    browser to ProConnect to complete an RP-initiated logout, which then redirects back
    to sites_conformes.proconnect.views.OIDCLogoutCallbackView (url name
    "oidc_logout_callback") to finally call auth.logout(). Since the Django session is
    still authenticated but unverified at that point, the base middleware would otherwise
    bounce this callback straight back to the 2FA code-entry screen, so auth.logout() would
    never run and the user would appear stuck on that screen after clicking "Sign out".
    """

    _allowed_url_names = VerifyUserMiddleware._allowed_url_names + ["oidc_logout_callback"]

    def _require_verified_user(self, request):
        static_url = settings.STATIC_URL.lstrip("/")
        media_url = settings.MEDIA_URL.lstrip("/")
        path = request.path_info.lstrip("/")
        if path.startswith(static_url) or (media_url and path.startswith(media_url)):
            return False
        return super()._require_verified_user(request)
