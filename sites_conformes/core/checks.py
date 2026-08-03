from django.core import checks
from django.core.exceptions import ImproperlyConfigured


@checks.register(checks.Tags.models)
def check_contentpage_model(app_configs, **kwargs):
    """
    Validate the SF_CONTENTPAGE_MODEL setting: the model must exist and
    inherit from AbstractContentPage.
    """
    from sites_conformes.core.abstract import AbstractContentPage
    from sites_conformes.core.model_utils import get_contentpage_model, get_contentpage_model_string

    errors = []

    try:
        model = get_contentpage_model()
    except ImproperlyConfigured as e:
        return [
            checks.Error(
                str(e),
                hint="Set SF_CONTENTPAGE_MODEL to an installed model, e.g. 'sites_conformes_core.ContentPage'.",
                id="sites_conformes.E001",
            )
        ]

    if not issubclass(model, AbstractContentPage):
        errors.append(
            checks.Error(
                f"SF_CONTENTPAGE_MODEL refers to model '{get_contentpage_model_string()}' "
                "that is not a subclass of sites_conformes.core.abstract.AbstractContentPage.",
                hint="Custom content page models must inherit from AbstractContentPage.",
                obj=model,
                id="sites_conformes.E002",
            )
        )

    return errors
