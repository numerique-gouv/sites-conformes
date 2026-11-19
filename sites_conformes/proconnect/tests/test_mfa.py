from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from sites_conformes.proconnect.mfa import PROCONNECT_MFA_SESSION_KEY, is_mfa_acr, is_session_verified_by_proconnect
from sites_conformes.proconnect.tests import requires_proconnect

User = get_user_model()

OIDC_BACKEND = "sites_conformes.proconnect.backends.OIDCAuthenticationBackend"
MODEL_BACKEND = "django.contrib.auth.backends.ModelBackend"


class IsMfaAcrTest(TestCase):
    def test_mfa_acr_values_are_accepted(self):
        for acr in ["eidas0-mfa", "eidas1-mfa", "eidas2", "eidas3"]:
            with self.subTest(acr=acr):
                self.assertTrue(is_mfa_acr({"acr": acr}))

    def test_other_acr_values_are_rejected(self):
        for payload in [{"acr": "eidas1"}, {"acr": ""}, {}, None]:
            with self.subTest(payload=payload):
                self.assertFalse(is_mfa_acr(payload))

    def test_default_acr_values_when_setting_is_missing(self):
        with self.settings():
            del settings.PROCONNECT_MFA_ACR_VALUES
            self.assertTrue(is_mfa_acr({"acr": "eidas1-mfa"}))
            self.assertFalse(is_mfa_acr({"acr": "eidas1"}))


class MissingSettingsTest(TestCase):
    """A host project of the package may define none of the ProConnect settings."""

    def test_session_is_not_verified_when_settings_are_missing(self):
        user = User.objects.create_user("bob", "bob@example.com", "pass")
        request = RequestFactory().get("/cms-admin/")
        SessionMiddleware(get_response=lambda r: None).process_request(request)
        request.user = user
        request.session[PROCONNECT_MFA_SESSION_KEY] = str(user.pk)

        with self.settings():
            del settings.PROCONNECT_ACTIVATED
            del settings.PROCONNECT_DELEGATE_2FA
            self.assertFalse(is_session_verified_by_proconnect(request))


@requires_proconnect
class ProconnectMfaLoginTest(TestCase):
    """
    The backend flags the request from the ID token "acr" claim, and the
    user_logged_in receiver stores that flag in the session once logged in.

    Needs the ProConnect app (its models and its user_logged_in receiver), so
    the backend is imported lazily for the module to load without it.
    """

    def setUp(self):
        self.user = User.objects.create_superuser("alice@example.com", "alice@example.com", "pass")
        self.request = RequestFactory().get("/oidc/callback/")
        SessionMiddleware(get_response=lambda r: None).process_request(self.request)

    def _proconnect_login(self, acr):
        from sites_conformes.proconnect.backends import OIDCAuthenticationBackend

        backend = OIDCAuthenticationBackend()
        backend.request = self.request
        user_info = {"sub": "alice-sub", "email": self.user.email}
        with mock.patch.object(backend, "get_userinfo", return_value=user_info):
            user = backend.get_or_create_user("access-token", "id-token", {"acr": acr})
        login(self.request, user, backend=OIDC_BACKEND)

    def test_login_with_mfa_acr_is_recorded(self):
        self._proconnect_login("eidas1-mfa")
        self.assertEqual(self.request.session[PROCONNECT_MFA_SESSION_KEY], str(self.user.pk))

    def test_login_without_mfa_acr_is_not_recorded(self):
        self._proconnect_login("eidas1")
        self.assertNotIn(PROCONNECT_MFA_SESSION_KEY, self.request.session)

    def test_password_login_clears_a_previous_proconnect_mfa(self):
        self.request.session[PROCONNECT_MFA_SESSION_KEY] = str(self.user.pk)
        login(self.request, self.user, backend=MODEL_BACKEND)
        self.assertNotIn(PROCONNECT_MFA_SESSION_KEY, self.request.session)
