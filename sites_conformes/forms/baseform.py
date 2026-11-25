import warnings

from dsfr.forms import DsfrBaseForm


class SitesConformesBaseForm(DsfrBaseForm):
    # Subclassing the Dsfr base form to set autofocus on the first error found when applicable

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_autofocus_on_first_error()


def __getattr__(name):
    # Deprecated alias kept for backward compatibility with projects using the old name.
    if name == "SitesFacilesBaseForm":
        warnings.warn(
            "SitesFacilesBaseForm is deprecated, use SitesConformesBaseForm instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return SitesConformesBaseForm
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
