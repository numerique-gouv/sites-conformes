from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from sites_conformes.proconnect.models import UserOIDC, WhitelistedEmailDomain

User = get_user_model()


def get_user_by_sub_or_email(sub: str, email: str, siret: str):
    """
    Get the user by its sub, and if not found, try by email.
    If the user is then found, create the UserOIDC entry (or update it if the sub has changed)
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

    Checks the email domain and returns True if it is a gov domain.
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

    Checks the email domain against the database and returns True if it is a gov domain.
    """
    email = user_info.get("email")
    domain = email.split("@")[1]
    if WhitelistedEmailDomain.objects.filter(domain=domain).count():
        result = {"status": "success"}
    else:
        result = {"status": "error", "message": _("User email domain not allowed.")}

    return result
