import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

default_app_config = "sites_conformes.apps.SitesConformesAppConfig"


def _get_version() -> str:
    """Numéro de version, avec pyproject.toml comme source unique de vérité.

    On le lit de deux façons complémentaires selon le mode de déploiement :
    1. via les métadonnées du paquet quand il a été installé (ex. `pip install`) ;
    2. sinon en lisant directement `pyproject.toml`, pour les instances qui tournent
       depuis une simple copie du dépôt (cas courant ici) où le paquet n'est pas installé.
    Retourne une chaîne vide si aucune des deux méthodes n'aboutit ; le reste du code gère ce cas.
    """
    try:
        return version("sites-conformes")
    except PackageNotFoundError:
        try:
            pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
            with pyproject.open("rb") as f:
                return tomllib.load(f)["project"]["version"]
        except (OSError, KeyError, tomllib.TOMLDecodeError):
            return ""


__version__ = _get_version()
