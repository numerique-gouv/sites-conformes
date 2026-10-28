from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.middleware import PublicCacheMiddleware


@override_settings(SF_PUBLIC_CACHE_MAX_AGE=60)
class PublicCacheMiddlewareTestCase(SimpleTestCase):
    def run_middleware(self, request=None, response=None):
        response = response or HttpResponse()
        middleware = PublicCacheMiddleware(lambda request: response)
        return middleware(request or RequestFactory().get("/"))

    def test_anonymous_page_is_cacheable(self):
        response = self.run_middleware()
        self.assertEqual(response.headers["Cache-Control"], "public, max-age=60")

    @override_settings(SF_PUBLIC_CACHE_MAX_AGE=0)
    def test_disabled_when_zero(self):
        response = HttpResponse()
        response.headers["Vary"] = "Cookie"
        response = self.run_middleware(response=response)
        self.assertNotIn("Cache-Control", response.headers)
        self.assertEqual(response.headers["Vary"], "Cookie")

    def test_private_with_a_session(self):
        request = RequestFactory().get("/")
        request.COOKIES[settings.SESSION_COOKIE_NAME] = "abc"
        response = HttpResponse()
        response.headers["Vary"] = "Cookie"
        response = self.run_middleware(request=request, response=response)
        self.assertEqual(response.headers["Cache-Control"], "private")
        self.assertEqual(response.headers["Vary"], "Cookie")

    def test_vary_cookie_is_removed_from_cacheable_responses(self):
        response = HttpResponse()
        response.headers["Vary"] = "Sec-Fetch-Dest, Accept-Language, Cookie"
        response = self.run_middleware(response=response)
        self.assertEqual(response.headers["Vary"], "Sec-Fetch-Dest, Accept-Language")

    def test_vary_is_dropped_when_only_cookie(self):
        response = HttpResponse()
        response.headers["Vary"] = "Cookie"
        response = self.run_middleware(response=response)
        self.assertNotIn("Vary", response.headers)

    def test_not_cached_when_setting_a_cookie(self):
        response = HttpResponse()
        response.set_cookie("csrftoken", "abc")
        response.headers["Vary"] = "Cookie"
        response = self.run_middleware(response=response)
        self.assertNotIn("Cache-Control", response.headers)
        self.assertEqual(response.headers["Vary"], "Cookie")

    def test_not_cached_when_not_successful(self):
        response = self.run_middleware(response=HttpResponse(status=404))
        self.assertNotIn("Cache-Control", response.headers)

    def test_not_cached_for_post(self):
        response = self.run_middleware(request=RequestFactory().post("/"))
        self.assertNotIn("Cache-Control", response.headers)

    def test_not_cached_for_admin(self):
        request = RequestFactory().get(f"/{settings.WAGTAILADMIN_PATH}")
        response = self.run_middleware(request=request)
        self.assertNotIn("Cache-Control", response.headers)

    def test_existing_header_is_kept(self):
        response = HttpResponse()
        response.headers["Cache-Control"] = "max-age=31536000, immutable"
        response = self.run_middleware(response=response)
        self.assertEqual(response.headers["Cache-Control"], "max-age=31536000, immutable")


@override_settings(SF_PUBLIC_CACHE_MAX_AGE=60)
class PublicCacheResponsesTestCase(WagtailPageTestCase):
    def test_home_page_is_cacheable_for_anonymous_visitors(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "public, max-age=60")
        self.assertNotIn("cookie", response.headers.get("Vary", "").lower())
        self.assertFalse(response.cookies)

    def test_home_page_is_not_cacheable_for_logged_in_users(self):
        user = self.create_superuser("admin")
        self.client.force_login(user)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "private")
