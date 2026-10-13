from django import forms

from sites_conformes.forms.autocomplete import AUTOCOMPLETE_FIELD_TYPES


class CustomEmailInputWidget(forms.EmailInput):
    """
    This is a custom input type for the email field, with refined
    extra attributes for cross-browser compatibility.
    """

    def __init__(self, attrs={}):
        attrs = {
            "autocapitalize": "off",
            "autocomplete": "email",
            "autocorrect": "off",
            "spellcheck": "false",
            **attrs,
        }

        super().__init__(attrs=attrs)


class AutocompleteSelect(forms.Select):
    """
    Select for the autocomplete token of a form field, exposing on each option
    the field types it is compatible with (used to filter the options in the admin).
    """

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            option["attrs"]["data-field-types"] = " ".join(sorted(AUTOCOMPLETE_FIELD_TYPES.get(value, ())))
        return option
