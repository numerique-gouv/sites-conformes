from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

from sites_conformes.dashboard.middleware import VerifyUserStaticFilesMiddleware

User = get_user_model()


class VerifyUserStaticFilesMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = VerifyUserStaticFilesMiddleware(get_response=lambda r: None)
        self.admin = User.objects.create_superuser("admin", "admin@test.com", "pass")

    def _request(self, path, user=None):
        request = self.factory.get(path)
        request.user = user if user is not None else self.admin
        return request

    def _request_with_session(self, path, user=None):
        request = self._request(path, user=user)
        SessionMiddleware(get_response=lambda r: None).process_request(request)
        request.session.save()
        return request

    # -- Static files

    @override_settings(WAGTAIL_2FA_REQUIRED=True)
    def test_wagtail_admin_static_file_does_not_require_verification(self):
        request = self._request("/static/wagtailadmin/js/vendor.js")
        self.assertFalse(self.middleware._require_verified_user(request))

    @override_settings(WAGTAIL_2FA_REQUIRED=True)
    def test_dsfr_module_js_does_not_require_verification(self):
        request = self._request("/static/dsfr/dist/dsfr/dsfr.module.min.js")
        self.assertFalse(self.middleware._require_verified_user(request))

    @override_settings(WAGTAIL_2FA_REQUIRED=True, STATIC_URL="/custom/static/")
    def test_custom_static_url_prefix_does_not_require_verification(self):
        request = self._request("/custom/static/admin.css")
        self.assertFalse(self.middleware._require_verified_user(request))

    # -- Media files

    @override_settings(WAGTAIL_2FA_REQUIRED=True, MEDIA_URL="/media/")
    def test_media_file_does_not_require_verification(self):
        request = self._request("/media/images/photo.jpg")
        self.assertFalse(self.middleware._require_verified_user(request))

    # -- Other URLs

    @override_settings(WAGTAIL_2FA_REQUIRED=True)
    def test_non_static_path_with_staff_user_requires_verification(self):
        request = self._request("/cms-admin/")
        self.assertTrue(self.middleware._require_verified_user(request))

    @override_settings(WAGTAIL_2FA_REQUIRED=True)
    def test_static_path_does_not_require_verification_even_if_otherwise_required(self):
        request = self._request("/static/file.js")
        self.assertFalse(self.middleware._require_verified_user(request))

    @override_settings(WAGTAIL_2FA_REQUIRED=False)
    def test_2fa_not_required_globally_for_user_without_device(self):
        request = self._request("/cms-admin/")
        self.assertFalse(self.middleware._require_verified_user(request))

    # -- Users who opted in to 2FA even though it isn't globally required

    @override_settings(WAGTAIL_2FA_REQUIRED=False)
    def test_2fa_still_required_for_user_with_confirmed_device(self):
        TOTPDevice.objects.create(user=self.admin, name="Device", confirmed=True)
        request = self._request("/cms-admin/")
        self.assertTrue(self.middleware._require_verified_user(request))

    @override_settings(WAGTAIL_2FA_REQUIRED=False)
    def test_unverified_user_with_confirmed_device_is_redirected_to_otp_screen(self):
        TOTPDevice.objects.create(user=self.admin, name="Device", confirmed=True)
        request = self._request_with_session("/cms-admin/")
        response = self.middleware.process_request(request)
        self.assertIsNotNone(response)
        self.assertIn(reverse("wagtail_2fa_auth"), response.url)

    @override_settings(WAGTAIL_2FA_REQUIRED=False)
    def test_static_path_does_not_require_verification_for_user_with_confirmed_device(self):
        TOTPDevice.objects.create(user=self.admin, name="Device", confirmed=True)
        request = self._request("/static/file.js")
        self.assertFalse(self.middleware._require_verified_user(request))

    @override_settings(WAGTAIL_2FA_REQUIRED=False)
    def test_otp_auth_screen_does_not_require_verification_for_user_with_confirmed_device(self):
        TOTPDevice.objects.create(user=self.admin, name="Device", confirmed=True)
        request = self._request(reverse("wagtail_2fa_auth"))
        self.assertFalse(self.middleware._require_verified_user(request))

    @override_settings(WAGTAIL_2FA_REQUIRED=True)
    def test_anonymous_user_does_not_require_verification(self):
        request = self._request("/cms-admin/", user=AnonymousUser())
        self.assertFalse(self.middleware._require_verified_user(request))

    @override_settings(WAGTAIL_2FA_REQUIRED=True)
    def test_non_staff_user_does_not_require_verification(self):
        non_staff = User.objects.create_user("user", "user@test.com", "pass")
        request = self._request("/cms-admin/", user=non_staff)
        self.assertFalse(self.middleware._require_verified_user(request))

    @override_settings(WAGTAIL_2FA_REQUIRED=True, MEDIA_URL="")
    def test_empty_media_url_does_not_crash(self):
        request = self._request("/cms-admin/")
        result = self.middleware._require_verified_user(request)
        self.assertTrue(result)

    # -- ProConnect (OIDC) logout callback

    @override_settings(WAGTAIL_2FA_REQUIRED=True)
    def test_oidc_logout_callback_does_not_require_verification(self):
        """
        Regression test: clicking "Sign out" on the 2FA code-entry screen redirects
        through ProConnect and back to the OIDC logout callback. If that callback were
        gated behind verification, auth.logout() inside it would never run, and the user
        would be bounced straight back to the 2FA code-entry screen instead of being
        logged out.
        """
        request = self._request("/oidc/logout-callback/")
        self.assertFalse(self.middleware._require_verified_user(request))
