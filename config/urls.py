from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.urls import include, path
from django.views.defaults import page_not_found, server_error
from django.views.generic.base import RedirectView, TemplateView
from django.views.i18n import JavaScriptCatalog
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.contrib.sitemaps.views import sitemap
from wagtail.documents import urls as wagtaildocs_urls

from config.api import api_router
from proconnect import urls as oidc_urls

urlpatterns = [
    path("sitemap.xml", sitemap, name="xml_sitemap"),
    path(settings.WAGTAILADMIN_PATH, include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("api/v2/", api_router.urls),
    path("favicon.ico", RedirectView.as_view(url="/static/dsfr/dist/favicon/favicon.ico", permanent=True)),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
] + static(settings.MEDIA_URL, document_root=getattr(settings, "MEDIA_ROOT", ""))

# Only add this on a dev machine, outside of tests
if not settings.TESTING and settings.DEBUG and "localhost" in settings.HOST_URL:
    urlpatterns += (path("__debug__/", include("debug_toolbar.urls")),)

if settings.SF_USE_DB_STORAGE:
    urlpatterns += [
        path("db-storage/", include("db_storage.urls")),
    ]

if settings.PROCONNECT_ACTIVATED:
    urlpatterns += [
        path("oidc/", include(oidc_urls)),
    ]

if settings.DEBUG or settings.TESTING:
    urlpatterns += i18n_patterns(
        path("404/", page_not_found, kwargs={"exception": Exception("Page not Found")}),
        path("500/", server_error),
        prefix_default_language=False,
    )

urlpatterns += i18n_patterns(
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    path("", include("content_manager.urls")),
    prefix_default_language=False,
)
