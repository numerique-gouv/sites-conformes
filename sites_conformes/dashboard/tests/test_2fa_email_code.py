import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from sites_conformes.dashboard.services import email_code

User = get_user_model()

OIDC_BACKEND = "sites_conformes.proconnect.backends.OIDCAuthenticationBackend"

LOCAL_LOGIN_DISABLED_SETTINGS = {
    "PROCONNECT_ACTIVATED": True,
    "SF_DISABLE_LOCAL_LOGIN": True,
    "AUTHENTICATION_BACKENDS": [OIDC_BACKEND],
}


@override_settings(DEFAULT_FROM_EMAIL="noreply@test.test", WAGTAIL_2FA_REQUIRED=True, **LOCAL_LOGIN_DISABLED_SETTINGS)
class EmailCodeDeviceFormTestCase(TestCase):
    """
    The 2FA device form asks for a code sent by email when the password can't be checked,
    see sites_conformes.dashboard.monkey_patches.patch_wagtail_2fa_device_form_password_check
    """

    def setUp(self):
        self.user = User.objects.create_superuser("test", "test@test.gouv.fr", "pass")
        self.client.force_login(self.user, backend=OIDC_BACKEND)
        self.url = reverse("wagtail_2fa_device_new")
        self.send_code_url = reverse("sites_conformes_2fa_email_code")

    def request_code(self):
        self.client.post(self.send_code_url, {"next": self.url})
        return re.search(r"^\d{6}$", mail.outbox[-1].body, re.MULTILINE).group()  # type: ignore

    def post_device(self, code):
        device = TOTPDevice.objects.get(user=self.user, confirmed=False)
        token = str(totp(device.bin_key)).zfill(6)
        return self.client.post(self.url, {"name": "My phone", "otp_token": token, "email_code": code})

    def test_admin_redirects_to_the_device_form(self):
        response = self.client.get(reverse("wagtailadmin_home"))

        self.assertRedirects(response, f"{self.url}?next={reverse('wagtailadmin_home')}")

    def test_form_asks_for_an_email_code_instead_of_the_password(self):
        response = self.client.get(self.url)

        self.assertNotContains(response, 'name="password"')
        self.assertContains(response, 'name="email_code"')
        self.assertContains(response, f'action="{self.send_code_url}"')

    def test_device_is_added_with_the_email_code(self):
        self.client.get(self.url)
        code = self.request_code()

        self.assertEqual(mail.outbox[0].to, ["test@test.gouv.fr"])

        response = self.post_device(code)

        self.assertRedirects(response, reverse("wagtail_2fa_device_list", kwargs={"user_id": self.user.id}))
        self.assertTrue(TOTPDevice.objects.get(user=self.user).confirmed)

    def test_wrong_code_is_rejected(self):
        self.client.get(self.url)
        code = self.request_code()
        wrong_code = "000000" if code != "000000" else "111111"

        response = self.post_device(wrong_code)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TOTPDevice.objects.get(user=self.user).confirmed)

    def test_code_is_rejected_without_request(self):
        self.client.get(self.url)

        response = self.post_device("123456")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TOTPDevice.objects.get(user=self.user).confirmed)

    def test_code_can_only_be_used_once(self):
        self.client.get(self.url)
        code = self.request_code()
        self.post_device(code)
        TOTPDevice.objects.update(confirmed=False)

        response = self.post_device(code)

        self.assertEqual(response.status_code, 200)

    def test_code_expires(self):
        self.client.get(self.url)
        code = self.request_code()

        with patch.object(email_code.time, "time", return_value=email_code.time.time() + email_code.CODE_VALIDITY + 1):
            response = self.post_device(code)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TOTPDevice.objects.get(user=self.user).confirmed)

    def test_code_is_rejected_after_too_many_attempts(self):
        self.client.get(self.url)
        code = self.request_code()
        wrong_code = "000000" if code != "000000" else "111111"
        for _attempt in range(email_code.MAX_ATTEMPTS):
            self.post_device(wrong_code)

        response = self.post_device(code)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TOTPDevice.objects.get(user=self.user).confirmed)

    def test_codes_cannot_be_requested_too_often(self):
        self.client.get(self.url)
        self.request_code()

        self.client.post(self.send_code_url, {"next": self.url})

        self.assertEqual(len(mail.outbox), 1)

    def test_send_code_does_not_redirect_outside_the_site(self):
        response = self.client.post(self.send_code_url, {"next": "https://example.com/"})

        self.assertRedirects(response, self.url, fetch_redirect_response=False)

    @override_settings(DEFAULT_FROM_EMAIL="")
    def test_device_cannot_be_added_without_email(self):
        response = self.client.get(self.url)

        self.assertNotContains(response, 'name="password"')
        self.assertNotContains(response, 'name="email_code"')
        self.assertNotContains(response, 'type="submit"')

        device = TOTPDevice.objects.get(user=self.user, confirmed=False)
        token = str(totp(device.bin_key)).zfill(6)
        response = self.client.post(self.url, {"name": "My phone", "otp_token": token})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TOTPDevice.objects.get(user=self.user).confirmed)


@override_settings(DEFAULT_FROM_EMAIL="noreply@test.test")
class PasswordDeviceFormTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("test", "test@test.gouv.fr", "pass")
        self.url = reverse("wagtail_2fa_device_new")

    def test_password_is_asked_after_a_password_login(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertContains(response, 'name="password"')
        self.assertNotContains(response, 'name="email_code"')

    def test_email_code_is_asked_after_a_proconnect_login(self):
        # Local login still enabled, but the session was opened through ProConnect
        self.client.force_login(self.user, backend=OIDC_BACKEND)

        response = self.client.get(self.url)

        self.assertNotContains(response, 'name="password"')
        self.assertContains(response, 'name="email_code"')
