"""
Confirmation code sent by email, asked instead of the current password in the 2FA device form
when that password can't be checked.

See sites_conformes.dashboard.monkey_patches.patch_wagtail_2fa_device_form_password_check
"""

import time

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.crypto import constant_time_compare, get_random_string, salted_hmac

PROCONNECT_BACKEND = "sites_conformes.proconnect.backends.OIDCAuthenticationBackend"
SESSION_KEY = "sites_conformes_email_code"
CODE_LENGTH = 6
CODE_VALIDITY = 5 * 60  # seconds
SEND_COOLDOWN = 60  # seconds
MAX_ATTEMPTS = 5


def password_check_available(request) -> bool:
    """
    The current password is only asked to users who logged in with it. Users who logged in
    through ProConnect may have no password, or no backend may accept passwords
    (see SF_DISABLE_LOCAL_LOGIN in config/settings.py).
    """
    return request.session.get(BACKEND_SESSION_KEY) != PROCONNECT_BACKEND


def email_code_available(user) -> bool:
    return bool(settings.DEFAULT_FROM_EMAIL and user.email)


def _hash(code: str) -> str:
    return salted_hmac(SESSION_KEY, code).hexdigest()


def seconds_before_next_code(request) -> int:
    data = request.session.get(SESSION_KEY)
    if not data:
        return 0
    return max(0, int(data["sent_at"] + SEND_COOLDOWN - time.time()))


def send_email_code(request) -> None:
    code = get_random_string(CODE_LENGTH, allowed_chars="0123456789")
    request.session[SESSION_KEY] = {
        "user_id": str(request.user.pk),
        "hash": _hash(code),
        "sent_at": time.time(),
        "attempts": 0,
    }

    context = {
        "code": code,
        "site_name": settings.WAGTAIL_SITE_NAME,
        "validity_minutes": CODE_VALIDITY // 60,
    }
    send_mail(
        subject=render_to_string("sites_conformes_admin/emails/2fa_email_code_subject.txt", context).strip(),
        message=render_to_string("sites_conformes_admin/emails/2fa_email_code.txt", context),
        from_email=None,
        recipient_list=[request.user.email],
    )


def check_email_code(request, code: str) -> bool:
    """
    Check the code against the last one sent to the user in this session.
    A code can only be used once, and is rejected once expired or after MAX_ATTEMPTS failed attempts.
    (It is kept in the session in that case, so that SEND_COOLDOWN still applies.)
    """
    data = request.session.get(SESSION_KEY)
    if not data or data["user_id"] != str(request.user.pk):
        return False

    if time.time() > data["sent_at"] + CODE_VALIDITY or data["attempts"] >= MAX_ATTEMPTS:
        return False

    if code and constant_time_compare(_hash(code), data["hash"]):
        del request.session[SESSION_KEY]
        return True

    data["attempts"] += 1
    request.session[SESSION_KEY] = data
    return False
