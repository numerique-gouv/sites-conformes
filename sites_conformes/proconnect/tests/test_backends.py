from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import SuspiciousOperation
from django.test import RequestFactory, TestCase, override_settings

from sites_conformes.dashboard.forms import DsfrPasswordResetForm
from sites_conformes.proconnect.backends import OIDCAuthenticationBackend
from sites_conformes.proconnect.exceptions import DuplicateEmailError
from sites_conformes.proconnect.models import UserOIDC, WhitelistedEmailDomain

User = get_user_model()

USER_INFO = {
    "sub": "newsub",
    "email": "jeanne.martin@beta.gouv.fr",
    "given_name": "Jeanne",
    "usual_name": "Martin",
    "siret": "13002526500013",
}


class GetUserinfoTestCase(TestCase):
    def setUp(self):
        self.backend = OIDCAuthenticationBackend()

    @patch("sites_conformes.proconnect.backends.requests.get")
    def test_json_response(self, mock_get):
        mock_get.return_value.json.return_value = {"sub": "abc"}

        userinfo = self.backend.get_userinfo("token", None, None)

        self.assertEqual(userinfo, {"sub": "abc"})
        self.assertEqual(mock_get.call_args.kwargs["headers"], {"Authorization": "Bearer token"})

    @patch("sites_conformes.proconnect.backends.requests.get")
    def test_signed_response_is_verified(self, mock_get):
        mock_get.return_value.json.side_effect = ValueError
        mock_get.return_value.text = "signed.jwt.token"

        with patch.object(self.backend, "verify_token", return_value={"sub": "abc"}) as mock_verify:
            userinfo = self.backend.get_userinfo("token", None, None)

        mock_verify.assert_called_once_with("signed.jwt.token")
        self.assertEqual(userinfo, {"sub": "abc"})

    @patch("sites_conformes.proconnect.backends.requests.get")
    def test_invalid_signed_response_raises(self, mock_get):
        mock_get.return_value.json.side_effect = ValueError
        mock_get.return_value.text = "invalid"

        with patch.object(self.backend, "verify_token", side_effect=Exception("bad signature")):
            with self.assertRaises(SuspiciousOperation):
                self.backend.get_userinfo("token", None, None)


class VerifyClaimsTestCase(TestCase):
    def test_claims_with_email_are_valid(self):
        self.assertTrue(OIDCAuthenticationBackend().verify_claims(USER_INFO))

    def test_claims_without_email_are_invalid(self):
        with self.assertLogs("sites_conformes.proconnect.backends", level="ERROR"):
            self.assertFalse(OIDCAuthenticationBackend().verify_claims({"sub": "abc"}))


@override_settings(PROCONNECT_USER_CREATION_FILTER=None, OIDC_CREATE_USER=True)
class GetOrCreateUserTestCase(TestCase):
    def setUp(self):
        self.backend = OIDCAuthenticationBackend()

        request = RequestFactory().get("/oidc/callback/")
        SessionMiddleware(lambda r: None).process_request(request)
        request._messages = FallbackStorage(request)
        self.backend.request = request

    def get_or_create_user(self, user_info):
        with patch.object(self.backend, "get_userinfo", return_value=user_info):
            return self.backend.get_or_create_user("token", None, None)

    def test_invalid_claims_raise(self):
        with self.assertLogs("sites_conformes.proconnect.backends", level="ERROR"):
            with self.assertRaises(SuspiciousOperation):
                self.get_or_create_user({"sub": "abc"})

    def test_new_user_is_created_without_usable_password(self):
        user = self.get_or_create_user(USER_INFO)

        self.assertEqual(user.username, "jeanne.martin@beta.gouv.fr")
        self.assertEqual(user.email, "jeanne.martin@beta.gouv.fr")
        self.assertEqual(user.first_name, "Jeanne")
        self.assertEqual(user.last_name, "Martin")
        self.assertFalse(user.has_usable_password())

        user_oidc = UserOIDC.objects.get(user=user)
        self.assertEqual(user_oidc.sub, "newsub")
        self.assertEqual(user_oidc.siret, "13002526500013")

    def test_new_user_cannot_request_password_reset(self):
        """Users created through ProConnect can only log in with it, so they get no password reset email."""
        user = self.get_or_create_user(USER_INFO)

        self.assertEqual(list(DsfrPasswordResetForm().get_users(user.email)), [])

    def test_existing_user_is_found_by_sub_and_updated(self):
        user = User.objects.create_user("old@beta.gouv.fr", "old@beta.gouv.fr", "pass", first_name="Jeanne")
        UserOIDC.objects.create(user=user, sub="newsub")

        result = self.get_or_create_user(USER_INFO)

        self.assertEqual(result, user)
        user.refresh_from_db()
        self.assertEqual(user.email, "jeanne.martin@beta.gouv.fr")
        self.assertEqual(user.last_name, "Martin")
        self.assertEqual(User.objects.count(), 1)

    def test_empty_values_do_not_overwrite_existing_ones(self):
        user = User.objects.create_user(
            USER_INFO["email"], USER_INFO["email"], "pass", first_name="Jeanne", last_name="Martin"
        )

        result = self.get_or_create_user({"sub": "newsub", "email": USER_INFO["email"], "given_name": ""})

        self.assertEqual(result, user)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Jeanne")
        self.assertEqual(user.last_name, "Martin")

    def test_existing_local_user_is_linked_by_email(self):
        user = User.objects.create_user(USER_INFO["email"], USER_INFO["email"], "pass")

        result = self.get_or_create_user(USER_INFO)

        self.assertEqual(result, user)
        self.assertEqual(UserOIDC.objects.get(user=user).sub, "newsub")
        # The local password is kept
        user.refresh_from_db()
        self.assertTrue(user.check_password("pass"))

    def test_inactive_user_is_refused(self):
        User.objects.create_user(USER_INFO["email"], USER_INFO["email"], "pass", is_active=False)

        with self.assertRaises(SuspiciousOperation):
            self.get_or_create_user(USER_INFO)

    def test_duplicate_email_is_refused(self):
        error = DuplicateEmailError(message="Duplicate email", email=USER_INFO["email"])
        with patch("sites_conformes.proconnect.backends.get_user_by_sub_or_email", side_effect=error):
            with self.assertRaisesMessage(SuspiciousOperation, "Duplicate email"):
                self.get_or_create_user(USER_INFO)

    @override_settings(OIDC_CREATE_USER=False)
    def test_no_user_is_created_if_creation_disabled(self):
        self.assertIsNone(self.get_or_create_user(USER_INFO))
        self.assertEqual(User.objects.count(), 0)

    @override_settings(PROCONNECT_USER_CREATION_FILTER="sites_conformes.proconnect.utils.email_domain_db_whitelist")
    def test_creation_filter_allows_whitelisted_domain(self):
        WhitelistedEmailDomain.objects.create(domain="beta.gouv.fr")

        user = self.get_or_create_user(USER_INFO)

        self.assertEqual(user.email, USER_INFO["email"])

    @override_settings(PROCONNECT_USER_CREATION_FILTER="sites_conformes.proconnect.utils.email_domain_db_whitelist")
    def test_creation_filter_refuses_other_domain(self):
        with self.assertRaises(SuspiciousOperation):
            self.get_or_create_user({**USER_INFO, "email": "someone@example.com"})

        self.assertEqual(User.objects.count(), 0)
        messages = [str(m) for m in get_messages(self.backend.request)]
        self.assertEqual(len(messages), 1)


class DuplicateEmailErrorTestCase(TestCase):
    def test_attributes(self):
        error = DuplicateEmailError(message="Duplicate", email="a@b.fr")

        self.assertEqual(error.message, "Duplicate")
        self.assertEqual(error.email, "a@b.fr")
        self.assertEqual(str(error), "Duplicate")
