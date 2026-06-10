from django.conf import settings
from wagtail_2fa.middleware import VerifyUserMiddleware


class VerifyUserStaticFilesMiddleware(VerifyUserMiddleware):
    """
    Extends VerifyUserMiddleware to skip 2FA verification for static and media file requests.
    Without this, when WAGTAIL_2FA_REQUIRED=True, static files served to an authenticated
    user without a configured 2FA device are redirected to the setup page, causing MIME errors.
    """

    def _require_verified_user(self, request):
        static_url = settings.STATIC_URL.lstrip("/")
        media_url = settings.MEDIA_URL.lstrip("/")
        path = request.path_info.lstrip("/")
        if path.startswith(static_url) or (media_url and path.startswith(media_url)):
            return False
        return super()._require_verified_user(request)
