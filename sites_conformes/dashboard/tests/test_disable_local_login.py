import os
import runpy
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

User = get_user_model()

MODEL_BACKEND = "django.contrib.auth.backends.ModelBackend"
OIDC_BACKEND = "sites_conformes.proconnect.backends.OIDCAuthenticationBackend"

LOCAL_LOGIN_DISABLED_SETTINGS = {
    "PROCONNECT_ACTIVATED": True,
    "SF_DISABLE_LOCAL_LOGIN": True,
    "AUTHENTICATION_BACKENDS": [OIDC_BACKEND],
    "WAGTAIL_PASSWORD_RESET_ENABLED": False,
    "WAGTAIL_PASSWORD_MANAGEMENT_ENABLED": False,
    "WAGTAILUSERS_PASSWORD_ENABLED": False,
}


def load_settings(**env):
    """Run config/settings.py in an isolated namespace, with the given environment variables."""
    with patch.dict(os.environ, env):
        return runpy.run_path(str(settings.BASE_DIR / "config" / "settings.py"))


class DisableLocalLoginSettingsTestCase(TestCase):
    def test_local_login_disabled_with_proconnect(self):
        loaded_settings = load_settings(PROCONNECT_ACTIVATED="True", SF_DISABLE_LOCAL_LOGIN="True")

        self.assertEqual(loaded_settings["AUTHENTICATION_BACKENDS"], [OIDC_BACKEND])
        self.assertFalse(loaded_settings["WAGTAIL_PASSWORD_RESET_ENABLED"])
        self.assertFalse(loaded_settings["WAGTAIL_PASSWORD_MANAGEMENT_ENABLED"])
        self.assertFalse(loaded_settings["WAGTAILUSERS_PASSWORD_ENABLED"])

    def test_local_login_enabled_with_proconnect(self):
        loaded_settings = load_settings(PROCONNECT_ACTIVATED="True", SF_DISABLE_LOCAL_LOGIN="False")

        self.assertEqual(loaded_settings["AUTHENTICATION_BACKENDS"], [MODEL_BACKEND, OIDC_BACKEND])
        self.assertNotIn("WAGTAIL_PASSWORD_MANAGEMENT_ENABLED", loaded_settings)
        self.assertNotIn("WAGTAILUSERS_PASSWORD_ENABLED", loaded_settings)

    def test_disable_local_login_is_ignored_without_proconnect(self):
        loaded_settings = load_settings(PROCONNECT_ACTIVATED="False", SF_DISABLE_LOCAL_LOGIN="True")

        # Django's default value, i.e. ModelBackend only
        self.assertNotIn("AUTHENTICATION_BACKENDS", loaded_settings)
        self.assertNotIn("WAGTAIL_PASSWORD_MANAGEMENT_ENABLED", loaded_settings)
        self.assertNotIn("WAGTAILUSERS_PASSWORD_ENABLED", loaded_settings)


class DisableLocalLoginViewsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("test", "test@test.test", "pass")
        self.login_url = reverse("wagtailadmin_login")

    def post_credentials(self):
        return self.client.post(self.login_url, {"username": "test", "password": "pass"})

    def test_password_login_works_by_default(self):
        self.post_credentials()

        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.user.pk))

    @override_settings(**LOCAL_LOGIN_DISABLED_SETTINGS)
    def test_password_login_is_rejected_when_disabled(self):
        response = self.post_credentials()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_form_display(self):
        cases = [
            # (PROCONNECT_ACTIVATED, SF_DISABLE_LOCAL_LOGIN, ProConnect button shown, login form shown)
            (False, False, False, True),
            (False, True, False, True),
            (True, False, True, True),
            (True, True, True, False),
        ]
        proconnect_url = reverse("oidc_authentication_init")

        for proconnect_activated, disable_local_login, has_proconnect, has_form in cases:
            with (
                self.subTest(proconnect_activated=proconnect_activated, disable_local_login=disable_local_login),
                override_settings(
                    PROCONNECT_ACTIVATED=proconnect_activated, SF_DISABLE_LOCAL_LOGIN=disable_local_login
                ),
            ):
                content = self.client.get(self.login_url).content.decode()

                self.assertEqual(f'href="{proconnect_url}"' in content, has_proconnect)
                self.assertEqual('id="login-form"' in content, has_form)

    @override_settings(**LOCAL_LOGIN_DISABLED_SETTINGS)
    def test_password_reset_is_disabled(self):
        response = self.client.get(reverse("wagtailadmin_password_reset"))

        self.assertEqual(response.status_code, 404)

    @override_settings(**LOCAL_LOGIN_DISABLED_SETTINGS)
    def test_password_change_is_disabled(self):
        self.client.force_login(self.user, backend=OIDC_BACKEND)

        response = self.client.get(reverse("wagtailadmin_account"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="password-new_password1"')

    @override_settings(**LOCAL_LOGIN_DISABLED_SETTINGS)
    def test_admin_cannot_set_a_password_on_user_creation(self):
        self.client.force_login(self.user, backend=OIDC_BACKEND)
        add_url = reverse("wagtailusers_users:add")

        response = self.client.get(add_url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="password1"')

        # A password sent anyway is ignored
        self.client.post(
            add_url,
            {
                "username": "agent",
                "email": "agent@test.gouv.fr",
                "first_name": "Agent",
                "last_name": "Public",
                "password1": "Un-mot-de-passe-solide-42",
                "password2": "Un-mot-de-passe-solide-42",
            },
        )

        agent = User.objects.get(username="agent")
        self.assertEqual(agent.password, "")
        self.assertFalse(agent.check_password("Un-mot-de-passe-solide-42"))

    def test_password_session_is_closed_when_local_login_is_disabled(self):
        self.client.force_login(self.user, backend=MODEL_BACKEND)

        with override_settings(**LOCAL_LOGIN_DISABLED_SETTINGS):
            response = self.client.get(reverse("wagtailadmin_home"))

        self.assertRedirects(
            response, f"{self.login_url}?next={reverse('wagtailadmin_home')}", fetch_redirect_response=False
        )
