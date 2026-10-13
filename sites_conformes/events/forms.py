from django import forms
from django.utils.translation import gettext_lazy as _

from sites_conformes.forms.baseform import SitesFacilesBaseForm


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

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error("date_to", _("The end date must be on or after the start date."))
        return cleaned_data
