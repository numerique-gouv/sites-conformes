from unittest import mock

from django.contrib.auth import get_user_model, login
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from sites_conformes.proconnect.backends import OIDCAuthenticationBackend
from sites_conformes.proconnect.mfa import PROCONNECT_MFA_SESSION_KEY, is_mfa_acr

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


class ProconnectMfaLoginTest(TestCase):
    """
    The backend flags the request from the ID token "acr" claim, and the
    user_logged_in receiver stores that flag in the session once logged in.
    """

    def setUp(self):
        self.user = User.objects.create_superuser("alice@example.com", "alice@example.com", "pass")
        self.request = RequestFactory().get("/oidc/callback/")
        SessionMiddleware(get_response=lambda r: None).process_request(self.request)

    def _proconnect_login(self, acr):
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
