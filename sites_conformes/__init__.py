from wagtail.utils.version import get_version

default_app_config = "sites_conformes.apps.SitesConformesAppConfig"

# major.minor.patch.release.number
# release must be one of alpha, beta, rc, or final
VERSION = (4, 0, 0, "final", 0)

__version__ = get_version(VERSION)
