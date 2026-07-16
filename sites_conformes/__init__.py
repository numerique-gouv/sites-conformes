from importlib.metadata import PackageNotFoundError, version

from ._version import __version__ as _fallback_version

default_app_config = "sites_conformes.apps.SitesConformesAppConfig"


def _get_version() -> str:
    """Numéro de version, avec `_version.py` comme source unique de vérité.

    On le lit de deux façons complémentaires selon le mode de déploiement :
    1. via les métadonnées du paquet quand il a été installé (ex. `pip install`) ;
    2. sinon en retombant sur `sites_conformes._version.__version__`, pour les instances
       qui tournent depuis une simple copie du dépôt (cas courant ici) où le paquet n'est
       pas installé. C'est la même valeur que celle utilisée par setuptools au build
       (cf. `[tool.setuptools.dynamic]` dans `pyproject.toml`).
    """
    try:
        return version("sites-conformes")
    except PackageNotFoundError:
        return _fallback_version


__version__ = _get_version()
