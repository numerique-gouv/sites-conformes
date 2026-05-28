from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase, override_settings
from wagtail_2fa.middleware import VerifyUserMiddleware

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
    def test_non_static_path_delegates_to_parent(self):
        request = self._request("/cms-admin/")
        with patch.object(VerifyUserMiddleware, "_require_verified_user", return_value=True) as mock_parent:
            result = self.middleware._require_verified_user(request)
        mock_parent.assert_called_once_with(request)
        self.assertTrue(result)

    @override_settings(WAGTAIL_2FA_REQUIRED=True)
    def test_static_path_does_not_call_parent(self):
        request = self._request("/static/file.js")
        with patch.object(VerifyUserMiddleware, "_require_verified_user") as mock_parent:
            self.middleware._require_verified_user(request)
        mock_parent.assert_not_called()

    @override_settings(WAGTAIL_2FA_REQUIRED=False)
    def test_2fa_not_required_globally(self):
        request = self._request("/cms-admin/")
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
        request = self._request("/some/path/")
        with patch.object(VerifyUserMiddleware, "_require_verified_user", return_value=False):
            result = self.middleware._require_verified_user(request)
        self.assertFalse(result)
