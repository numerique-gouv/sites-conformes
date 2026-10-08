from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.middleware import NoIndexMiddleware


class NoIndexMiddlewareTestCase(SimpleTestCase):
    def run_middleware(self, path="/"):
        middleware = NoIndexMiddleware(lambda request: HttpResponse())
        return middleware(RequestFactory().get(path))

    @override_settings(SF_NOINDEX=True)
    def test_header_is_set_when_enabled(self):
        response = self.run_middleware()
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow")

    @override_settings(SF_NOINDEX=False)
    def test_header_is_absent_when_disabled(self):
        response = self.run_middleware()
        self.assertNotIn("X-Robots-Tag", response.headers)


class NoIndexResponsesTestCase(WagtailPageTestCase):
    paths = ["/", "/robots.txt"]

    @override_settings(SF_NOINDEX=True)
    def test_responses_carry_the_header_when_enabled(self):
        for path in self.paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow")

    @override_settings(SF_NOINDEX=False)
    def test_responses_do_not_carry_the_header_when_disabled(self):
        for path in self.paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("X-Robots-Tag", response.headers)
