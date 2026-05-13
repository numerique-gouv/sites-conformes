from django.forms import Media, widgets


class DsfrIconPickerWidget(widgets.TextInput):
    template_name = "sites_conformes_content_manager/widgets/dsfr-icon-picker-widget.html"

    def __init__(self, attrs=None):
        default_attrs = {}
        attrs = attrs or {}
        attrs = {**default_attrs, **attrs}
        super().__init__(attrs=attrs)

    @property
    def media(self):
        return Media(
            css={"all": ["css/icon-picker.css", "dsfr/dist/utility/utility.min.css"]},
            js=["django-dsfr/icon-picker/assets/js/universal-icon-picker.min.js"],
        )
