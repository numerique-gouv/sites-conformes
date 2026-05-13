"""Authentication backends for ProConnect."""

import logging

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import SuspiciousOperation
from django.utils.crypto import get_random_string
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _
from mozilla_django_oidc.auth import (
    OIDCAuthenticationBackend as MozillaOIDCAuthenticationBackend,
)

from sites_conformes.proconnect.exceptions import DuplicateEmailError
from sites_conformes.proconnect.models import UserOIDC
from sites_conformes.proconnect.utils import get_user_by_sub_or_email

logger = logging.getLogger(__name__)
User = get_user_model()


class OIDCAuthenticationBackend(MozillaOIDCAuthenticationBackend):
    """Custom OpenID Connect (OIDC) Authentication Backend.

    This class overrides the default OIDC Authentication Backend to accommodate differences
    in the User and Identity models, and handles signed and/or encrypted UserInfo response.
    """

    def get_userinfo(self, access_token, id_token, payload):
        """Return user details dictionary.

        Parameters:
        - access_token (str): The access token.
        - id_token (str): The id token (unused).
        - payload (dict): The token payload (unused).

        Note: The id_token and payload parameters are unused in this implementation,
        but were kept to preserve base method signature.

        Note: It handles signed and/or encrypted UserInfo Response. It is required by
        ProConnect, which follows the OIDC standard. It forces us to override the
        base method, which deal with 'application/json' response.

        Returns:
        - dict: User details dictionary obtained from the OpenID Connect user endpoint.
        """
        user_response = requests.get(
            self.OIDC_OP_USER_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
            verify=self.get_settings("OIDC_VERIFY_SSL", True),
            timeout=self.get_settings("OIDC_TIMEOUT", None),
            proxies=self.get_settings("OIDC_PROXY", None),
        )
        user_response.raise_for_status()

        try:
            userinfo = user_response.json()
        except ValueError:
            try:
                userinfo = self.verify_token(user_response.text)
            except Exception as e:
                raise SuspiciousOperation(_("Invalid response format or token verification failed")) from e

        return userinfo

    def verify_claims(self, claims):
        """
        Verify the presence of essential claims and the "sub" (which is mandatory as defined
        by the OIDC specification) to decide if authentication should be allowed.
        """
        essential_claims = settings.USER_OIDC_ESSENTIAL_CLAIMS
        missing_claims = [claim for claim in essential_claims if claim not in claims]

        if missing_claims:
            logger.error("Missing essential claims: %s", missing_claims)
            return False

        return True

    def get_or_create_user(self, access_token, id_token, payload):
        """Return a User based on userinfo. Create a new user if no match is found."""
        user_info = self.get_userinfo(access_token, id_token, payload)

        if not self.verify_claims(user_info):
            raise SuspiciousOperation("Claims verification failed.")

        sub = user_info["sub"]
        email = user_info.get("email")
        first_name = user_info.get("given_name")
        last_name = user_info.get("usual_name")
        siret = user_info.get("siret", "")

        user_properties = {
            "username": email,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
        }

        try:
            user = get_user_by_sub_or_email(sub, email, siret)
        except DuplicateEmailError as err:
            raise SuspiciousOperation(err.message) from err

        if user:
            if not user.is_active:
                raise SuspiciousOperation(_("User account is disabled"))
            self.update_user_if_needed(user, user_properties)
        elif self.get_settings("OIDC_CREATE_USER", True):
            user_creation_filter = self.get_settings("PROCONNECT_USER_CREATION_FILTER", None)
            if user_creation_filter:
                user_creation_filter_method = import_string(user_creation_filter)
                filter_passed = user_creation_filter_method(user_info)
                if filter_passed["status"] == "success":
                    user = self.create_user_custom(sub, user_info, user_properties)
                else:
                    messages.add_message(self.request, messages.ERROR, filter_passed["message"])
                    raise SuspiciousOperation(filter_passed["message"])
            else:
                user = self.create_user_custom(sub, user_info, user_properties)

        return user

    def create_user_custom(self, sub, user_info, user_properties):
        """
        The actual creation of the user
        """
        user = User.objects.create(password=get_random_string(42), **user_properties)
        siret = user_info.get("siret", "")
        _user_claims = UserOIDC.objects.create(user=user, sub=sub, siret=siret)

        return user

    def update_user_if_needed(self, user, user_properties):
        """Update user properties if they have changed."""
        has_changed = any(value and value != getattr(user, key) for key, value in user_properties.items())
        if has_changed:
            updated_properties = {key: value for key, value in user_properties.items() if value}
            self.UserModel.objects.filter(id=user.id).update(**updated_properties)
