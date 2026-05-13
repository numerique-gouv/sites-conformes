from django import forms
from django.utils.translation import gettext_lazy as _

from config.forms.baseform import SitesFacilesBaseForm


class EventSearchForm(SitesFacilesBaseForm):
    """Main form for events page list."""

    date_from = forms.DateField(
        label=_("Start date"),
        required=False,
        widget=forms.TextInput(attrs={"type": "date"}),
    )

    date_to = forms.DateField(
        label=_("End date"),
        required=False,
        widget=forms.TextInput(attrs={"type": "date"}),
    )
