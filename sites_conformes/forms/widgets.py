from django import forms


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
