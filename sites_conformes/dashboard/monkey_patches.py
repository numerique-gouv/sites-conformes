"""
Monkey patches applied to third-party libraries at startup.

Applied from ``DashboardConfig.ready()``.
"""

from django.utils.translation import gettext_lazy as _
from django_otp.plugins.otp_totp.models import TOTPDevice
from wagtail_2fa import utils as wagtail_2fa_utils


def patch_wagtail_2fa_new_unconfirmed_device():
    """
    Fix "invalid 2FA code" errors during device setup in wagtail-2fa 1.8.0.

    ``DeviceCreateView.device`` calls ``utils.new_unconfirmed_device(user)`` on
    every GET of the "2fa/devices/new" setup page. The original implementation
    unconditionally deletes any existing unconfirmed TOTPDevice for the user
    and creates a brand new one with a freshly randomized ``key`` (secret):

        def new_unconfirmed_device(user):
            delete_unconfirmed_devices(user)
            num = TOTPDevice.objects.filter(user=user).count()
            return TOTPDevice.objects.create(
                name=_("Device #%s") % (num + 1), user=user, confirmed=False
            )

    GET is not idempotent here: if the setup page is loaded a second time
    (page reload, a second tab, browser prefetch, a corporate proxy/AV
    re-fetching links, a retried request after a slow response, ...) after the
    user has already scanned the QR code but before they submit the 6-digit
    code, the secret is silently regenerated and the old row deleted. The
    authenticator app still holds the orphaned secret, so every code it
    produces is then rejected by ``DeviceForm.clean_otp_token`` ->
    ``TOTPDevice.verify_token``, which validates against whichever unconfirmed
    device happens to exist in the DB at POST time.

    This patch changes "delete + recreate on every GET" into "reuse the
    existing unconfirmed device if one already exists", while still creating
    a device the first time (or after a device was confirmed / removed). The
    QR code view (``DeviceQRCodeView``, via ``utils.get_unconfirmed_device``)
    and the POST path are untouched, so once a device is reused its secret
    stays stable for the lifetime of an in-progress setup.

    Bug present in wagtail-2fa 1.8.0 (latest at time of writing).
    Upstream issue: https://github.com/labd/wagtail-2fa/issues/TODO
    Remove this patch once fixed upstream and the ``wagtail-2fa`` dependency
    in pyproject.toml is upgraded past the fixed version.
    """

    def new_unconfirmed_device(user):
        existing_device = wagtail_2fa_utils.get_unconfirmed_device(user)
        if existing_device is not None:
            return existing_device

        num = TOTPDevice.objects.filter(user=user).count()
        return TOTPDevice.objects.create(name=_("Device #%s") % (num + 1), user=user, confirmed=False)

    wagtail_2fa_utils.new_unconfirmed_device = new_unconfirmed_device
