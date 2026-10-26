from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()


class OIDCLogoutViewTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("user@beta.gouv.fr", "user@beta.gouv.fr", "pass")
        self.url = reverse("wagtailadmin_logout")

    def login_with_id_token(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["oidc_id_token"] = "the-id-token"
        session.save()

    def test_anonymous_user_is_redirected(self):
        response = self.client.post(self.url)

        self.assertRedirects(response, settings.LOGOUT_REDIRECT_URL, fetch_redirect_response=False)

    def test_user_without_id_token_is_logged_out_locally(self):
        self.client.force_login(self.user)

        response = self.client.post(self.url)

        self.assertRedirects(response, settings.LOGOUT_REDIRECT_URL, fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_user_with_id_token_is_redirected_to_provider(self):
        self.login_with_id_token()

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)
        location = urlparse(response["Location"])
        self.assertEqual(f"{location.scheme}://{location.netloc}{location.path}", settings.OIDC_OP_LOGOUT_ENDPOINT)

        query = parse_qs(location.query)
        self.assertEqual(query["id_token_hint"], ["the-id-token"])
        self.assertTrue(query["post_logout_redirect_uri"][0].endswith(reverse("oidc_logout_callback")))

        # The state is kept in session for the callback, and the user is still logged in until then
        state = query["state"][0]
        self.assertIn(state, self.client.session["oidc_states"])
        self.assertIn("_auth_user_id", self.client.session)

    @override_settings(OIDC_OP_LOGOUT_ENDPOINT=None)
    def test_user_is_logged_out_locally_without_provider_endpoint(self):
        self.login_with_id_token()

        response = self.client.post(self.url)

        self.assertRedirects(response, settings.LOGOUT_REDIRECT_URL, fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)


class OIDCLogoutCallbackViewTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("user@beta.gouv.fr", "user@beta.gouv.fr", "pass")
        self.url = reverse("oidc_logout_callback")

    def test_anonymous_user_is_redirected(self):
        response = self.client.get(self.url)

        self.assertRedirects(response, settings.LOGOUT_REDIRECT_URL, fetch_redirect_response=False)

    def test_unknown_state_is_refused(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url, {"state": "unknown"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("_auth_user_id", self.client.session)

    def test_valid_state_logs_user_out(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["oidc_states"] = {"known-state": {}}
        session.save()

        response = self.client.get(self.url, {"state": "known-state"})

        self.assertRedirects(response, settings.LOGOUT_REDIRECT_URL, fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
