from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice
from wagtail_2fa import utils

User = get_user_model()


class NewUnconfirmedDevicePatchTest(TestCase):
    """
    Regression test for
    sites_conformes.dashboard.monkey_patches.patch_wagtail_2fa_new_unconfirmed_device.
    """

    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.test", "pass")

    def test_first_call_creates_a_device(self):
        device = utils.new_unconfirmed_device(self.user)
        self.assertEqual(TOTPDevice.objects.filter(user=self.user).count(), 1)
        self.assertFalse(device.confirmed)

    def test_second_call_reuses_the_same_device_and_key(self):
        first = utils.new_unconfirmed_device(self.user)
        second = utils.new_unconfirmed_device(self.user)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.key, second.key)
        self.assertEqual(TOTPDevice.objects.filter(user=self.user).count(), 1)

    def test_new_device_created_again_once_previous_one_is_confirmed(self):
        first = utils.new_unconfirmed_device(self.user)
        first.confirmed = True
        first.save()

        second = utils.new_unconfirmed_device(self.user)

        self.assertNotEqual(first.pk, second.pk)
        self.assertFalse(second.confirmed)


@override_settings(WAGTAIL_2FA_REQUIRED=True)
class DeviceCreateViewDoubleGetTest(TestCase):
    """
    End-to-end regression test: simulates a duplicate GET of the 2FA setup
    page (page reload / second tab / prefetch) before the user submits their
    code, and asserts the secret does not change and setup still succeeds.
    """

    PASSWORD = "correcthorsebatterystaple"

    def setUp(self):
        self.user = User.objects.create_superuser("alice", "alice@test.test", self.PASSWORD)
        self.client.login(username="alice", password=self.PASSWORD)
        self.url = reverse("wagtail_2fa_device_new")

    def _current_device(self):
        return TOTPDevice.objects.get(user=self.user, confirmed=False)

    def test_two_sequential_gets_keep_the_same_secret(self):
        self.client.get(self.url)
        first_key = self._current_device().key

        self.client.get(self.url)
        second_key = self._current_device().key

        self.assertEqual(first_key, second_key)
        self.assertEqual(TOTPDevice.objects.filter(user=self.user).count(), 1)

    def test_submitting_code_after_a_reload_succeeds(self):
        self.client.get(self.url)
        self.client.get(self.url)  # simulate the reload/duplicate GET

        device = self._current_device()
        token = str(totp(device.bin_key)).zfill(6)

        response = self.client.post(
            self.url,
            {"name": "My phone", "otp_token": token, "password": self.PASSWORD},
        )

        self.assertRedirects(
            response,
            reverse("wagtail_2fa_device_list", kwargs={"user_id": self.user.id}),
        )
        device.refresh_from_db()
        self.assertTrue(device.confirmed)
