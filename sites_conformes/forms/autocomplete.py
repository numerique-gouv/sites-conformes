"""
Autocomplete tokens for form fields, used to identify the input purpose (WCAG 2.1 criterion 1.3.5).

See https://www.w3.org/Translations/WCAG21-fr/#input-purposes
"""

from django.utils.translation import gettext_lazy as _

TEXT = "singleline"
TEXTAREA = "multiline"
EMAIL = "email"
URL = "url"
NUMBER = "number"
DATE = "date"
DROPDOWN = "dropdown"

# Grouped by theme, rendered as <optgroup> in the admin
AUTOCOMPLETE_CHOICES = (
    (
        _("Identity"),
        (
            ("name", _("Full name")),
            ("honorific-prefix", _("Prefix or title")),
            ("given-name", _("Given name")),
            ("additional-name", _("Additional names")),
            ("family-name", _("Family name")),
            ("honorific-suffix", _("Suffix")),
            ("nickname", _("Nickname")),
            ("organization-title", _("Job title")),
            ("username", _("Username")),
            ("organization", _("Organization")),
            ("bday", _("Birthday")),
            ("bday-day", _("Day of birth")),
            ("bday-month", _("Month of birth")),
            ("bday-year", _("Year of birth")),
            ("sex", _("Gender identity")),
            ("language", _("Preferred language")),
            ("photo", _("Photograph, icon or other image")),
        ),
    ),
    (
        _("Postal address"),
        (
            ("street-address", _("Street address (multiple lines)")),
            ("address-line1", _("Street address (line 1)")),
            ("address-line2", _("Street address (line 2)")),
            ("address-line3", _("Street address (line 3)")),
            ("address-level4", _("Address level 4 (most fine-grained)")),
            ("address-level3", _("Address level 3")),
            ("address-level2", _("Address level 2 (city)")),
            ("address-level1", _("Address level 1 (broadest, e.g. state)")),
            ("postal-code", _("Postal code")),
            ("country", _("Country code")),
            ("country-name", _("Country name")),
        ),
    ),
    (
        _("Contact details"),
        (
            ("email", _("Email address")),
            ("tel", _("Full telephone number, including country code")),
            ("tel-country-code", _("Telephone country code")),
            ("tel-national", _("Telephone number without the country code")),
            ("tel-area-code", _("Telephone area code")),
            ("tel-local", _("Telephone number without the country code and area code")),
            ("tel-local-prefix", _("First part of the local telephone number")),
            ("tel-local-suffix", _("Second part of the local telephone number")),
            ("tel-extension", _("Telephone extension code")),
            ("url", _("Home page or other web page")),
            ("impp", _("Instant messaging protocol endpoint URL")),
        ),
    ),
    (
        _("Payment"),
        (
            ("cc-name", _("Full name as given on the payment instrument")),
            ("cc-given-name", _("Given name as given on the payment instrument")),
            ("cc-additional-name", _("Additional names as given on the payment instrument")),
            ("cc-family-name", _("Family name as given on the payment instrument")),
            ("cc-number", _("Payment instrument number")),
            ("cc-exp", _("Payment instrument expiration date")),
            ("cc-exp-month", _("Payment instrument expiration month")),
            ("cc-exp-year", _("Payment instrument expiration year")),
            ("cc-csc", _("Payment instrument security code")),
            ("cc-type", _("Payment instrument type")),
            ("transaction-currency", _("Transaction currency")),
            ("transaction-amount", _("Transaction amount")),
        ),
    ),
)

AUTOCOMPLETE_TOKENS = [token for _group, choices in AUTOCOMPLETE_CHOICES for token, _label in choices]

# Field types (see FormField.CHOICES) each autocomplete token can be used with.
# Checkbox, checkboxes, radio and hidden fields do not support the autocomplete attribute.
AUTOCOMPLETE_FIELD_TYPES = {
    "name": {TEXT},
    "honorific-prefix": {TEXT, DROPDOWN},
    "given-name": {TEXT},
    "additional-name": {TEXT},
    "family-name": {TEXT},
    "honorific-suffix": {TEXT},
    "nickname": {TEXT},
    "organization-title": {TEXT},
    "username": {TEXT},
    "organization": {TEXT},
    "street-address": {TEXTAREA},
    "address-line1": {TEXT},
    "address-line2": {TEXT},
    "address-line3": {TEXT},
    "address-level4": {TEXT},
    "address-level3": {TEXT},
    "address-level2": {TEXT},
    "address-level1": {TEXT},
    "country": {TEXT, DROPDOWN},
    "country-name": {TEXT, DROPDOWN},
    "postal-code": {TEXT},
    "cc-name": {TEXT},
    "cc-given-name": {TEXT},
    "cc-additional-name": {TEXT},
    "cc-family-name": {TEXT},
    "cc-number": {TEXT},
    "cc-exp": {TEXT},
    "cc-exp-month": {TEXT, NUMBER, DROPDOWN},
    "cc-exp-year": {TEXT, NUMBER, DROPDOWN},
    "cc-csc": {TEXT},
    "cc-type": {TEXT, DROPDOWN},
    "transaction-currency": {TEXT, DROPDOWN},
    "transaction-amount": {TEXT, NUMBER},
    "language": {TEXT, DROPDOWN},
    "bday": {TEXT, DATE},
    "bday-day": {TEXT, NUMBER, DROPDOWN},
    "bday-month": {TEXT, NUMBER, DROPDOWN},
    "bday-year": {TEXT, NUMBER, DROPDOWN},
    "sex": {TEXT, DROPDOWN},
    "url": {URL},
    "photo": {URL},
    "tel": {TEXT},
    "tel-country-code": {TEXT},
    "tel-national": {TEXT},
    "tel-area-code": {TEXT},
    "tel-local": {TEXT},
    "tel-local-prefix": {TEXT},
    "tel-local-suffix": {TEXT},
    "tel-extension": {TEXT},
    "email": {EMAIL},
    "impp": {URL},
}

# Field types for which the autocomplete value cannot be left empty, with their default value.
MANDATORY_AUTOCOMPLETE = {EMAIL: "email"}


def get_autocomplete_choices_for(field_type: str) -> list[str]:
    """Returns the autocomplete tokens compatible with the given field type."""
    return [token for token in AUTOCOMPLETE_TOKENS if field_type in AUTOCOMPLETE_FIELD_TYPES[token]]


def is_autocomplete_compatible(token: str, field_type: str) -> bool:
    return field_type in AUTOCOMPLETE_FIELD_TYPES.get(token, set())
