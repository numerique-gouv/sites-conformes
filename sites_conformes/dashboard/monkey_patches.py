"""
Monkey patches applied to third-party libraries at startup.

Applied from ``DashboardConfig.ready()``.
"""

import logging

from django import forms
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django_otp.plugins.otp_totp.models import TOTPDevice
from wagtail_2fa import utils as wagtail_2fa_utils

logger = logging.getLogger(__name__)


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
    Upstream issue: https://github.com/labd/wagtail-2fa/issues/282
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


def patch_wagtail_2fa_device_create_view_success_message():
    """
    Show a success message once two-factor authentication setup is confirmed.

    ``DeviceCreateView.form_valid`` (wagtail-2fa) confirms the device and
    redirects to the device list page, but does not add any confirmation
    message, so a user who just finished setup lands on that page with no
    feedback that it actually worked.
    """

    from wagtail_2fa.views import DeviceCreateView

    original_form_valid = DeviceCreateView.form_valid

    def form_valid(self, form):
        response = original_form_valid(self, form)
        messages.success(
            self.request,
            _("Two-factor authentication has been successfully configured."),
        )
        return response

    DeviceCreateView.form_valid = form_valid


def patch_wagtail_2fa_device_form_field_order():
    """
    Show "Current password" before "OTP token" in the add-device form.

    ``DeviceForm`` (wagtail-2fa) declares its fields in the order
    ``otp_token``, ``name``, ``password``, but ``Meta.fields = ["name",
    "otp_token"]`` only pulls in real model fields (just ``name``) before
    Django merges in the declared fields, so the field actually ends up
    displayed as name -> otp_token -> password. Asking for the password
    before the OTP token reads more naturally, so reorder them here rather
    than forking the form.
    """

    from wagtail_2fa.forms import DeviceForm

    original_init = DeviceForm.__init__

    def __init__(self, request, **kwargs):
        original_init(self, request, **kwargs)
        self.order_fields(["name", "password", "otp_token"])

    DeviceForm.__init__ = __init__


def patch_wagtail_2fa_device_form_password_check():
    """
    Ask for a code sent by email instead of the current password in the add/edit device form
    when the user logged in through ProConnect.

    ``DeviceForm`` (wagtail-2fa) checks the password with ``authenticate()``, which always
    fails when the local login is disabled (PROCONNECT_ACTIVATED and SF_DISABLE_LOCAL_LOGIN:
    ModelBackend is removed from AUTHENTICATION_BACKENDS) or when the user has no password
    (accounts created through ProConnect). With WAGTAIL_2FA_REQUIRED=True, such a user would
    be redirected to the add-device form on every admin page without any way to submit it.

    If no email can be sent (DEFAULT_FROM_EMAIL not set, or user without email address),
    adding a device is blocked: it must not be possible without any confirmation.
    """

    from wagtail_2fa.forms import DeviceForm

    from sites_conformes.dashboard.services.email_code import (
        check_email_code,
        email_code_available,
        password_check_available,
    )

    original_init = DeviceForm.__init__
    original_clean = DeviceForm.clean

    def __init__(self, request, **kwargs):
        original_init(self, request, **kwargs)
        self.email_code_unavailable = False
        if password_check_available(request):
            return

        del self.fields["password"]
        if email_code_available(request.user):
            self.fields["email_code"] = forms.CharField(
                label=_("Code received by email"),
                max_length=6,
                widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "inputmode": "numeric"}),
            )
            self.order_fields(["name", "email_code", "otp_token"])
        else:
            self.email_code_unavailable = True

    def clean_email_code(self):
        code = self.cleaned_data.get("email_code")
        if not check_email_code(self.request, code):
            raise forms.ValidationError(_("Invalid or expired code. Please request a new one."))
        return code

    def clean(self):
        if self.email_code_unavailable:
            raise forms.ValidationError(_("Two-factor authentication can't be set up without sending an email."))
        return original_clean(self)

    DeviceForm.__init__ = __init__
    DeviceForm.clean_email_code = clean_email_code
    DeviceForm.clean = clean


def patch_wagtail_2fa_token_form_device_selection():
    """
    Fix "invalid 2FA code" errors on login with django-otp >= 1.7.4.

    Since django-otp 1.7.4 (https://github.com/django-otp/django-otp/pull/194),
    ``OTPAuthenticationFormMixin._verify_token`` no longer tries each of the
    user's devices when no ``otp_device`` was submitted: it raises a
    ``device_required`` validation error instead. ``TokenForm`` (wagtail-2fa
    1.8.0) has no ``otp_device`` field at all, so every login attempt fails,
    whatever the code (and otp_form_v6.html renders any form error as
    "Invalid code").

    When no device was chosen, try each of the user's confirmed TOTP devices
    in turn, which restores the pre-1.7.4 behaviour for the only device type
    wagtail-2fa supports. Throttling still applies per device, via the
    original ``_verify_token``.

    Remove this patch once wagtail-2fa selects the device itself and the
    ``wagtail-2fa`` dependency in pyproject.toml is upgraded past that version.
    """

    from wagtail_2fa.forms import TokenForm

    original_verify_token = TokenForm._verify_token

    def _verify_token(self, user, token, device=None):
        if device is not None:
            return original_verify_token(self, user, token, device)

        devices = TOTPDevice.objects.devices_for_user(user, confirmed=True)
        if not devices:
            return original_verify_token(self, user, token, None)

        error = None
        for candidate in devices:
            try:
                return original_verify_token(self, user, token, candidate)
            except forms.ValidationError as e:
                error = e
        raise error

    TokenForm._verify_token = _verify_token


def patch_wagtail_2fa_token_form_report_unexpected_errors():
    """
    Report unexpected 2FA login errors to Sentry.

    otp_form_v6.html renders any ``TokenForm`` error as "Invalid code", which
    hid the django-otp 1.7.4 ``device_required`` regression (see
    ``patch_wagtail_2fa_token_form_device_selection``) from both users and us.

    A wrong or missing code is the user's doing and stays silent. Any other
    error carrying a code is logged at ERROR level, which the Sentry logging
    integration sends as an event. Errors without a code are django-otp's
    throttling messages ("too many failed attempts"), also user-driven, so
    they stay silent too.
    """

    from wagtail_2fa.forms import TokenForm

    expected_error_codes = {"invalid_token", "token_required"}
    original_clean = TokenForm.clean

    def clean(self):
        try:
            return original_clean(self)
        except forms.ValidationError as e:
            if e.code is not None and e.code not in expected_error_codes:
                logger.error(
                    "Unexpected 2FA login error for user %s: [%s] %s",
                    self.user.pk,
                    e.code,
                    " ".join(e.messages),
                )
            raise

    TokenForm.clean = clean
