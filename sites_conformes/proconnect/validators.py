from django.core import validators
from django.utils.translation import gettext_lazy as _

sub_validator = validators.RegexValidator(
    regex=r"^[\w.@+-:]+\Z",
    message=_("Enter a valid sub. This value may contain only letters, numbers, and @/./+/-/_/: characters."),
)
