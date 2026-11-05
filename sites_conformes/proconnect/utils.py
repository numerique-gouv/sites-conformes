from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from sites_conformes.proconnect.models import UserOIDC, WhitelistedEmailDomain

User = get_user_model()


def get_user_by_sub_or_email(sub: str, email: str, siret: str):
    """
    Get the user by its sub, and if not found, try by email.
    If the user is then found, create the UserOIDC entry (or update it if the sub has changed)

    Returns the user, or None if no user matches: the account creation is then
    handled by the authentication backend.
    """
    user_oidc = UserOIDC.objects.select_related("user").filter(sub=sub).first()
    if user_oidc:
        return user_oidc.user

    user = User.objects.filter(email=email).first()

    if user:
        user_oidc, _created = UserOIDC.objects.update_or_create(user=user, defaults={"sub": sub, "siret": siret})
        user_oidc.save()

    return user


def email_domain_basic_whitelist(user_info: dict) -> dict:
    """
    Example method of a filter for account creation when using ProConnect.

    Accepts the emails ending with ".gouv.fr". Returns {"status": "success"} if the
    domain is allowed, or {"status": "error", "message": ...} otherwise.

    To use it, set the `PROCONNECT_USER_CREATION_FILTER` setting to
    "sites_conformes.proconnect.utils.email_domain_basic_whitelist".
    """
    email = user_info.get("email")
    if email.endswith(".gouv.fr"):
        result = {"status": "success"}
    else:
        result = {"status": "error", "message": _("User email domain not allowed.")}

    return result


def email_domain_db_whitelist(user_info: dict) -> dict:
    """
    Example method of a filter for account creation when using ProConnect.

    Accepts the emails whose domain is listed in the `WhitelistedEmailDomain` table
    (exact match, subdomains are not included). Returns {"status": "success"} if the
    domain is allowed, or {"status": "error", "message": ...} otherwise.

    To use it, set the `PROCONNECT_USER_CREATION_FILTER` setting to
    "sites_conformes.proconnect.utils.email_domain_db_whitelist".
    """
    email = user_info.get("email")
    domain = email.split("@")[1]
    if WhitelistedEmailDomain.objects.filter(domain=domain).count():
        result = {"status": "success"}
    else:
        result = {"status": "error", "message": _("User email domain not allowed.")}

    return result
