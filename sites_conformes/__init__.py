from importlib.metadata import PackageNotFoundError, version

default_app_config = "sites_conformes.apps.SitesConformesAppConfig"

# Source unique de vérité pour le numéro de version : le champ `version` de pyproject.toml,
# exposé via les métadonnées du paquet installé. Fallback vide si le paquet n'est pas installé
# (ex. exécution depuis les sources sans `pip install`), ce que le reste du code gère gracieusement.
try:
    __version__ = version("sites-conformes")
except PackageNotFoundError:
    __version__ = ""
