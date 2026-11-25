import logging

from django.apps import apps
from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, QueryDict
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.cache import patch_cache_control, patch_vary_headers
from wagtail.admin.auth import permission_denied
from wagtail.admin.localization import get_localized_response
from wagtail.models import Page

from sites_conformes.core.models import CmsDsfrConfig
from sites_conformes.core.multisite_isolation import (
    SITE_SCOPED_VIEWSETS,
    get_sites_for_user,
    is_multisite_isolation_active,
    is_page_in_scope,
    is_superuser_only_view,
)

logger = logging.getLogger(__name__)

# Sec-Fetch-Dest values indicating the document is loaded inside a frame.
# The header is sent by Chrome 80+, Firefox 90+ and Safari 16.4+. Older
# browsers never send it and always get the standalone template, even when
# embedded (graceful degradation: the page still renders, with full chrome).
_FRAME_FETCH_DESTS = ("iframe", "frame")


class NoIndexMiddleware:
    """
    Ask search engines not to index anything served by this instance.

    Enabled with the ``SF_NOINDEX`` setting. The header is used rather than
    ``robots.txt`` because a ``Disallow`` rule blocks crawling, not indexing,
    and would prevent crawlers from reading the directive.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if settings.SF_NOINDEX:
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response


class PublicCacheMiddleware:
    """
    Let browsers and the CDN cache pages served to anonymous visitors.

    Enabled with the ``SF_PUBLIC_CACHE_MAX_AGE`` setting (in seconds). Only
    successful ``GET``/``HEAD`` responses get ``Cache-Control: public``, and
    never when:

    - the request carries a session (logged-in user, password-protected page,
      pending messages): these responses get ``Cache-Control: private``,
    - the response sets a cookie (CSRF token of a form, new session): a shared
      cache would hand it to every visitor,
    - the response already has a ``Cache-Control`` header (static files…),
    - the request targets the admin.

    ``Cookie`` is removed from the ``Vary`` header of cacheable responses:
    ``SessionMiddleware`` adds it as soon as the session is read (e.g. through
    ``request.user``), which keeps most CDNs from caching the page. Without a
    session nor a cookie set, the page is the same for every anonymous
    visitor. A logged-in user may therefore get the anonymous version from the
    CDN, for at most ``SF_PUBLIC_CACHE_MAX_AGE`` seconds.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        max_age = getattr(settings, "SF_PUBLIC_CACHE_MAX_AGE", 0)
        if max_age <= 0 or response.has_header("Cache-Control"):
            return response

        if settings.SESSION_COOKIE_NAME in request.COOKIES:
            patch_cache_control(response, private=True)
        elif self._is_cacheable(request, response):
            patch_cache_control(response, public=True, max_age=max_age)
            self._remove_vary_cookie(response)

        return response

    @staticmethod
    def _is_cacheable(request: HttpRequest, response: HttpResponse) -> bool:
        return (
            request.method in ("GET", "HEAD")
            and response.status_code == 200
            and not response.cookies
            and not request.path_info.lstrip("/").startswith(settings.WAGTAILADMIN_PATH.lstrip("/"))
        )

    @staticmethod
    def _remove_vary_cookie(response: HttpResponse) -> None:
        if not response.has_header("Vary"):
            return
        vary = [header.strip() for header in response["Vary"].split(",")]
        vary = [header for header in vary if header and header.lower() != "cookie"]
        if vary:
            response["Vary"] = ", ".join(vary)
        else:
            del response["Vary"]


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

        directive = f"frame-ancestors {value}"
        # Keep a policy already set by the view (e.g. Wagtail's document serve view
        # sends "default-src 'none'" to block scripts in uploaded files)
        existing = response.headers.get("Content-Security-Policy")
        if existing and "frame-ancestors" not in existing:
            directive = f"{existing.rstrip('; ')}; {directive}"
        elif existing:
            return
        response.headers["Content-Security-Policy"] = directive

    @staticmethod
    def _is_admin_request(request: HttpRequest) -> bool:
        admin_path = settings.WAGTAILADMIN_PATH.lstrip("/")
        return request.path_info.lstrip("/").startswith(admin_path)


class MultisiteIsolationMiddleware:
    """
    Restricts the admin views that the viewsets and hooks cannot reach to the sites of
    the user, when the multisite isolation is enabled (see
    ``sites_conformes.core.multisite_isolation``):

    - the page explorer returns a 404 for a page outside of the user's sites, so that its
      title is not shown;
    - the page chooser, opened on such a page (for instance the parent of a link to
      another site, already set), opens at the root of the tree instead, filtered by the
      ``construct_page_chooser_queryset`` hook;
    - the bulk actions and the wagtail-localize views of a model using
      ``SiteScopedViewSetMixin`` return a 404 for an object outside of the scope;
    - the views of a model using ``SuperuserOnlyViewSetMixin`` redirect to the dashboard
      with the "permission denied" message of the Wagtail admin, or return a 403 for an
      XHR request.

    Must be placed after the authentication middleware.
    """

    BULK_ACTION_PERMISSIONS = {"delete": ["delete"], "publish": ["publish"], "unpublish": ["publish"]}

    def __init__(self, get_response):
        """
        Maps the names of the restricted views to the method checking each one.
        """
        self.get_response = get_response
        self.handlers = {
            "wagtailadmin_explore": self.check_explored_page,
            "wagtailadmin_explore_results": self.check_explored_page,
            "wagtailadmin_choose_page_child": self.check_chooser_parent_page,
            "wagtail_bulk_action": self.check_bulk_action,
            "wagtail_localize:submit_snippet_translation": self.check_snippet,
            "wagtail_localize:snippets_api_detail": self.check_snippet,
            "wagtail_localize:update_translations": self.check_translation_source,
        }

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Passes the request on: the checks happen in process_view, once the view is known.
        """
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Runs the check of the view, if any, for a restricted user.
        """
        if not is_multisite_isolation_active():
            return None
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated or user.is_superuser:
            return None
        if is_superuser_only_view(request.resolver_match, view_kwargs):
            # The chooser does not check the permissions on the model: the response of the
            # Wagtail admin is given here, in the language of the user
            return get_localized_response(permission_denied, request)
        handler = self.handlers.get(request.resolver_match.view_name)
        if handler is None:
            return None
        return handler(request, **view_kwargs)

    @staticmethod
    def is_page_hidden(request, page_id) -> bool:
        """
        Whether the page exists and is outside of the sites of the user.
        """
        page = Page.objects.filter(pk=page_id).first()
        return page is not None and not is_page_in_scope(page, get_sites_for_user(request.user))

    def check_explored_page(self, request, parent_page_id, **kwargs):
        """
        Returns a 404 in the explorer for a page outside of the sites of the user.
        """
        if self.is_page_hidden(request, parent_page_id):
            raise Http404

    def check_chooser_parent_page(self, request, parent_page_id, **kwargs):
        """
        Redirects the page chooser to the root when it is opened on a page outside of the sites of the user.
        """
        if self.is_page_hidden(request, parent_page_id):
            url = reverse("wagtailadmin_choose_page")
            if query_string := request.META.get("QUERY_STRING"):
                url = f"{url}?{query_string}"
            return redirect(url)

    @staticmethod
    def get_viewset(app_label, model_name):
        """
        Returns the SiteScopedViewSetMixin viewset of the model, or None if it is not site-scoped.
        """
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            return None
        return SITE_SCOPED_VIEWSETS.get(model)

    def check_bulk_action(self, request, app_label, model_name, action, **kwargs):
        """
        Restricts a bulk action on a site-scoped model to the objects of the scope.
        """
        viewset = self.get_viewset(app_label, model_name)
        if viewset is None:
            return
        actions = self.BULK_ACTION_PERMISSIONS.get(action)
        ids = request.GET.getlist("id")
        if "all" in ids:
            # Wagtail would act on every object of the model: only keep those of the scope
            pks = viewset.filter_queryset(viewset.model._default_manager.all(), request.user, actions).values_list(
                "pk", flat=True
            )
            query = request.GET.copy()
            query.setlist("id", [str(pk) for pk in pks])
            request.GET = QueryDict(query.urlencode())
            request.META["QUERY_STRING"] = query.urlencode()
            return
        in_scope = viewset.filter_queryset(viewset.model._default_manager.filter(pk__in=ids), request.user, actions)
        if in_scope.count() != len(set(ids)):
            raise Http404

    def check_snippet(self, request, app_label, model_name, pk, **kwargs):
        """
        Returns a 404 for a wagtail-localize view of an object outside of the scope.
        """
        viewset = self.get_viewset(app_label, model_name)
        if viewset is not None and not viewset.is_in_scope(request.user, pk):
            raise Http404

    def check_translation_source(self, request, translation_source_id, **kwargs):
        """
        Returns a 404 when syncing the translations of an object outside of the scope.
        """
        from wagtail_localize.models import TranslationSource

        source = TranslationSource.objects.filter(pk=translation_source_id).first()
        if source is None:
            return
        viewset = SITE_SCOPED_VIEWSETS.get(source.specific_content_type.model_class())
        if viewset is None:
            return
        try:
            instance = source.get_source_instance()
        except viewset.model.DoesNotExist:
            return
        if not viewset.is_in_scope(request.user, instance.pk):
            raise Http404
