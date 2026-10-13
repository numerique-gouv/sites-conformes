from django.templatetags.static import static
from django.utils.html import format_html
from wagtail import hooks


@hooks.register("insert_editor_js")
def editor_js():
    """Inject JavaScript filtering the autocomplete options of form fields by field type."""
    return format_html(
        '<script src="{}"></script>',
        static("sites_conformes_forms/js/autocomplete-filter.js"),
    )
