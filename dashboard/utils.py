from datetime import date

import requests
from packaging.version import Version

from content_manager import __version__ as actual_version

LATEST_RELEASE_URL = "https://api.github.com/repos/numerique-gouv/sites-faciles/releases/latest"
INFORMATION_URL = "https://raw.githubusercontent.com/Luzzzi/test-information-panel/main/test.json"


def is_last_version(installed_version, latest_version):
    try:
        return Version(installed_version) >= Version(latest_version)
    except Exception:
        return True


def push_version_notification(items):
    items = []
    try:
        release_res = requests.get(LATEST_RELEASE_URL, timeout=5)
        release_res.raise_for_status()
        tag = release_res.json().get("tag_name", "").lstrip("v")
        if is_last_version(actual_version, tag):
            items.insert(
                0,
                {
                    "type": "info",
                    "title": f"Une nouvelle version de Sites Conformes est disponible ({tag})",
                    "description": (
                        f"Vous utilisez une version obsolète"
                        f"{f' ({actual_version})' if actual_version else ''}. "
                        "Rapprochez-vous de la personne qui a installé votre site "
                        "pour réaliser la mise à jour."
                    ),
                    "url": "https://github.com/numerique-gouv/sites-faciles/releases",
                },
            )
        return items
    except Exception:
        pass


def get_all_notifications():
    items = []
    push_version_notification(items)
    try:
        res = requests.get(INFORMATION_URL, timeout=5)
        res.raise_for_status()
        data = res.json()
        # cache.set(INFORMATION_CACHE_KEY, data, INFORMATION_CACHE_TIMEOUT)
    except Exception:
        data = {}

    today = date.today()
    for item in data.get("items", []):
        try:
            end_date = item.get("end_date")
            if not end_date or date.fromisoformat(end_date) >= today:
                items.append(item)
        except Exception:
            items.append(item)
    return items
