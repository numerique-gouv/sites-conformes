from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_query_string(value: str):
    """
    Validates that a query string:
    - starts with '?'
    - does not contain '#'
    (only criteria, per
      https://developer.mozilla.org/en-US/docs/Web/URI/Reference/Query)
    """
    if not value.startswith("?"):
        raise ValidationError(_("Query string must start with '?'."))

    if "#" in value:
        raise ValidationError(_("Query string must not contain '#'."))
