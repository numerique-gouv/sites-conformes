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

    PASSWORD = "correcthorsebatterystaple"

    def setUp(self):
        self.user = User.objects.create_superuser("alice", "alice@test.test", self.PASSWORD)
        TOTPDevice.objects.create(user=self.user, name="Device", confirmed=True)
        self.client.login(username="alice", password=self.PASSWORD)

    def test_sign_out_button_skips_client_side_validation(self):
        response = self.client.get(reverse("wagtail_2fa_auth"))
        content = response.content.decode()

        sign_out_button_start = content.index('formaction="')
        button_markup = content[max(0, sign_out_button_start - 200) : sign_out_button_start]

        self.assertIn("formnovalidate", button_markup)
