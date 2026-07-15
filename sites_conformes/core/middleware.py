import logging

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.cache import patch_vary_headers

from sites_conformes.core.models import CmsDsfrConfig

logger = logging.getLogger(__name__)

# Sec-Fetch-Dest values indicating the document is loaded inside a frame.
# The header is sent by Chrome 80+, Firefox 90+ and Safari 16.4+. Older
# browsers never send it and always get the standalone template, even when
# embedded (graceful degradation: the page still renders, with full chrome).
_FRAME_FETCH_DESTS = ("iframe", "frame")


class IframeMiddleware:
    """
    Iframe embedding support:

    - flags requests coming from an iframe (``request.iframe``) so templates
      can render a stripped-down layout,
    - emits a ``Content-Security-Policy: frame-ancestors`` directive built
      from the per-site ``CmsDsfrConfig.iframe_allow_origins`` setting.

    ``X-Frame-Options`` is intentionally left to Django's
    ``XFrameOptionsMiddleware`` (see ``X_FRAME_OPTIONS`` in settings): it only
    acts as a legacy fallback, as browsers supporting ``frame-ancestors``
    ignore it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.iframe = request.headers.get("Sec-Fetch-Dest") in _FRAME_FETCH_DESTS

        response = self.get_response(request)

        self._set_frame_ancestors(request, response)
        patch_vary_headers(response, ("Sec-Fetch-Dest",))

        return response

    def _set_frame_ancestors(self, request: HttpRequest, response: HttpResponse) -> None:
        value = "'self'"

        # Never relax framing for the back office: only front-office pages
        # may be embedded by the configured external origins.
        if not self._is_admin_request(request):
            try:
                config = CmsDsfrConfig.for_request(request)
                origins = [line.strip() for line in config.iframe_allow_origins.splitlines() if line.strip()]
                if origins:
                    value = " ".join(["'self'", *(f"https://{origin}" for origin in origins)])
            except Exception:
                # Fail closed, but never silently: a misconfiguration here
                # would otherwise disable embedding without any trace.
                logger.warning(
                    "IframeMiddleware: could not resolve allowed iframe origins, falling back to 'self'",
                    exc_info=True,
                )

        response.headers["Content-Security-Policy"] = f"frame-ancestors {value}"

    @staticmethod
    def _is_admin_request(request: HttpRequest) -> bool:
        admin_path = settings.WAGTAILADMIN_PATH.lstrip("/")
        return request.path_info.lstrip("/").startswith(admin_path)
