from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from wagtail.models import Page, Site
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.middleware import IframeMiddleware
from sites_conformes.core.models import CmsDsfrConfig, ContentPage
from sites_conformes.core.validators import validate_iframe_allow_origins

User = get_user_model()


class ValidateIframeAllowOriginsTestCase(SimpleTestCase):
    def test_accepts_bare_domains(self):
        for value in [
            "",
            "\n  \n",
            "example.com",
            "sub.example.com",
            "example.com\ncartes.gouv.fr\n",
            "  example.com  \n\n  cartes.gouv.fr",
        ]:
            with self.subTest(value=value):
                validate_iframe_allow_origins(value)

    def test_rejects_invalid_lines(self):
        for value in [
            "https://example.com",
            "example.com/path",
            "example.com:8443",
            "*.example.com",
            "example.com evil.com",
            "-bad.example.com",
            "example.com\nhttps://sneaky.com",
        ]:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_iframe_allow_origins(value)


class IframeMiddlewareTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = Site.objects.get(is_default_site=True)

    def run_middleware(self, path="/", view_response=None, **extra):
        middleware = IframeMiddleware(lambda request: view_response or HttpResponse())
        request = self.factory.get(path, **extra)
        return request, middleware(request)

    def set_origins(self, origins: str):
        config = CmsDsfrConfig.for_site(self.site)
        config.iframe_allow_origins = origins
        config.save()

    def test_defaults_to_self(self):
        _, response = self.run_middleware()
        self.assertEqual(response.headers["Content-Security-Policy"], "frame-ancestors 'self'")

    def test_configured_origins_are_allowed(self):
        self.set_origins("example.com\n\n  cartes.gouv.fr  ")
        _, response = self.run_middleware()
        self.assertEqual(
            response.headers["Content-Security-Policy"],
            "frame-ancestors 'self' https://example.com https://cartes.gouv.fr",
        )

    def test_admin_is_never_embeddable_by_external_origins(self):
        self.set_origins("example.com")
        _, response = self.run_middleware(f"/{settings.WAGTAILADMIN_PATH}pages/")
        self.assertEqual(response.headers["Content-Security-Policy"], "frame-ancestors 'self'")

    def test_vary_header_contains_sec_fetch_dest(self):
        view_response = HttpResponse(headers={"Vary": "Cookie"})
        _, response = self.run_middleware(view_response=view_response)
        self.assertIn("Sec-Fetch-Dest", response.headers["Vary"])
        self.assertIn("Cookie", response.headers["Vary"])

    def test_request_iframe_flag(self):
        cases = [
            ({"HTTP_SEC_FETCH_DEST": "iframe"}, True),
            ({"HTTP_SEC_FETCH_DEST": "frame"}, True),
            ({"HTTP_SEC_FETCH_DEST": "document"}, False),
            ({}, False),
        ]
        for extra, expected in cases:
            with self.subTest(extra=extra):
                request, _ = self.run_middleware(**extra)
                self.assertEqual(request.iframe, expected)


class IframeTemplateSelectionTestCase(WagtailPageTestCase):
    def setUp(self):
        home_page = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.content_page = home_page.add_child(
            instance=ContentPage(
                title="Page de contenu",
                slug="content-page",
                owner=self.admin,
            )
        )
        self.content_page.save()

    def test_standalone_template_by_default(self):
        response = self.client.get(self.content_page.get_url())
        self.assertTemplateUsed(response, "sites_conformes_core/standalone.html")
        self.assertTemplateNotUsed(response, "sites_conformes_core/iframe.html")
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")

    def test_iframe_template_when_embedded(self):
        response = self.client.get(self.content_page.get_url(), HTTP_SEC_FETCH_DEST="iframe")
        self.assertTemplateUsed(response, "sites_conformes_core/iframe.html")
        self.assertTemplateNotUsed(response, "sites_conformes_core/standalone.html")
