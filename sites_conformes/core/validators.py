import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Bare hostname (RFC 1123 labels). No scheme, no port, no path, no wildcard.
_HOSTNAME_RE = re.compile(r"^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(\.(?!-)[a-zA-Z0-9-]{1,63}(?<!-))*$")


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


def validate_iframe_allow_origins(value: str):
    """
    Validates that every non-empty line is a bare domain name
    (e.g. 'example.com').

    Schemes, ports, paths and wildcards are rejected: the middleware builds
    the CSP frame-ancestors directive by prefixing each line with
    'https://', so anything else would produce a malformed or overbroad
    policy.
    """
    for line in value.splitlines():
        domain = line.strip()
        if domain and not _HOSTNAME_RE.match(domain):
            raise ValidationError(
                _(
                    "'%(domain)s' is not a valid domain. Enter one bare domain per line, "
                    "without scheme, path or wildcard (e.g. 'example.com')."
                ),
                params={"domain": domain},
            )
