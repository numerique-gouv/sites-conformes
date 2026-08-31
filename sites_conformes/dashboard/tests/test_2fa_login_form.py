from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

User = get_user_model()


@override_settings(WAGTAIL_2FA_REQUIRED=True)
class OtpFormSignOutButtonTest(TestCase):
    """
    Regression test: on the "enter your two-factor authentication code"
    screen, the "Sign out" button must work even though the otp_token field
    is empty and marked ``required``. Without ``formnovalidate`` on that
    button, browsers block the form submission client-side (native HTML5
    validation), so clicking "Sign out" silently does nothing and the user
    stays stuck on the code-entry screen.
    """

    def setUp(self):
        self.user = User.objects.create_superuser("alice", "alice@test.test", "pass")
        TOTPDevice.objects.create(user=self.user, name="Device", confirmed=True)
        self.client.login(username="alice", password="pass")

    def test_sign_out_button_skips_client_side_validation(self):
        response = self.client.get(reverse("wagtail_2fa_auth"))
        content = response.content.decode()

        sign_out_button_start = content.index('formaction="')
        button_markup = content[max(0, sign_out_button_start - 200) : sign_out_button_start]

        self.assertIn("formnovalidate", button_markup)

    def test_sign_out_button_logs_the_user_out(self):
        """
        Simulates the browser submitting the "Sign out" button: a POST to
        wagtailadmin_logout with no otp_token, since the whole point of
        formnovalidate is to let that submission through despite the empty
        required field. The user must actually be logged out, not bounced
        back to the code-entry screen.
        """
        response = self.client.post(reverse("wagtailadmin_logout"))

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)


@override_settings(WAGTAIL_2FA_REQUIRED=True)
class OtpFormCustomTextTest(TestCase):
    """
    The "enter your two-factor authentication code" screen customizes the
    default wagtail-2fa copy: it adds a reminder paragraph pointing users to
    their authenticator app, and gives the otp_token field an explicit label
    and help text (the field otherwise falls back to Django's untranslated
    auto-generated label "Otp token" with no help text).
    """

    def setUp(self):
        self.user = User.objects.create_superuser("alice", "alice@test.test", "pass")
        TOTPDevice.objects.create(user=self.user, name="Device", confirmed=True)
        self.client.login(username="alice", password="pass")

    def test_reminder_paragraph_is_shown(self):
        response = self.client.get(reverse("wagtail_2fa_auth"))
        content = response.content.decode()

        self.assertIn(
            "Ouvrez votre application d’authentification (Aegis, Bitwarden, Google Authenticator, "
            "Microsoft Authenticator...) pour obtenir le code à entrer ci-dessous.",
            content,
        )

    def test_otp_field_has_custom_label_and_help_text(self):
        """
        The site's default language is French, so these msgids (shared with
        the add-device form, see device_form.html) render as their existing
        French translations rather than verbatim.
        """
        response = self.client.get(reverse("wagtail_2fa_auth"))
        content = response.content.decode()

        self.assertIn("Code de sécurité", content)
        self.assertIn("Entrez le code à six chiffres affiché dans l’application.", content)
        self.assertNotIn("Otp token", content)
