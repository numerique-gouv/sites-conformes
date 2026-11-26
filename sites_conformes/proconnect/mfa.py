"""
Delegation of two-factor authentication (2FA) to ProConnect.

When ``PROCONNECT_DELEGATE_2FA`` is enabled, ProConnect is asked for a
multi-factor authentication (see ``OIDC_AUTH_REQUEST_EXTRA_PARAMS`` in
config/settings.py) and a ProConnect login whose ID token ``acr`` claim
confirms it is not asked for the local wagtail-2fa code again (see
``sites_conformes.dashboard.middleware.VerifyUserStaticFilesMiddleware``).

The ``acr`` claim is always checked, as required by ProConnect: a login without
a confirmed MFA still goes through the local 2FA.
See https://partenaires.proconnect.gouv.fr/docs/fournisseur-service/double_authentification

This module must not import any model: the dashboard middleware imports it even
when the ProConnect app is not installed. For the same reason, the settings are
read with a default value: a host project may not define them.
"""

from django.conf import settings

PROCONNECT_MFA_SESSION_KEY = "proconnect_mfa_user_id"

# ProConnect "acr" values asserting a multi-factor authentication.
# Can be overridden with the PROCONNECT_MFA_ACR_VALUES setting.
DEFAULT_MFA_ACR_VALUES = ["eidas0-mfa", "eidas1-mfa", "eidas2", "eidas3"]


def is_mfa_acr(id_token_payload) -> bool:
    """Whether the ID token claims assert a multi-factor authentication."""
    acr_values = getattr(settings, "PROCONNECT_MFA_ACR_VALUES", DEFAULT_MFA_ACR_VALUES)
    return (id_token_payload or {}).get("acr") in acr_values


def record_proconnect_mfa(sender, request, user, **kwargs):
    """
    ``user_logged_in`` receiver: remember in the session whether this login was a
    ProConnect login with a confirmed MFA.

    ``OIDCAuthenticationBackend`` flags the request before ``auth.login()`` is
    called. The flag is stored afterwards rather than in the backend, since
    ``auth.login()`` may flush the session. It is tied to the user so that it
    can never cover another account, and is cleared by any other login.
    """
    if request is None or not hasattr(request, "session"):
        return

    if getattr(request, "proconnect_mfa", False):
        request.session[PROCONNECT_MFA_SESSION_KEY] = str(user.pk)
    else:
        request.session.pop(PROCONNECT_MFA_SESSION_KEY, None)


def is_session_verified_by_proconnect(request) -> bool:
    """
    Whether the second factor of this session was already checked by ProConnect.

    Also checks PROCONNECT_ACTIVATED, so that turning ProConnect off makes
    sessions opened through it ask for the local 2FA code again.
    """
    if not (getattr(settings, "PROCONNECT_ACTIVATED", False) and getattr(settings, "PROCONNECT_DELEGATE_2FA", False)):
        return False

    session = getattr(request, "session", None)
    if session is None:
        return False

    return session.get(PROCONNECT_MFA_SESSION_KEY) == str(request.user.pk)
