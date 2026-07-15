from datetime import date

import requests
from django.conf import settings
from django.core.cache import cache
from packaging.version import Version

from sites_conformes import __version__ as actual_version

VALID_TYPES = ["info", "warning", "alert"]
REQUIRED_FIELDS = ["type", "title", "start_date"]


def is_last_version(installed_version, latest_version):
    return Version(installed_version) >= Version(latest_version)


def is_displayable_notification(item):
    """Vérifie qu'une notification est bien formée ET affichable aujourd'hui."""

    for field in REQUIRED_FIELDS:
        if not item.get(field):
            return False

    if item.get("type") not in VALID_TYPES:
        return False

    today = date.today()

    try:
        if date.fromisoformat(item["start_date"]) > today:
            return False
    except ValueError:
        return False

    end_date_str = item.get("end_date")
    if end_date_str:
        try:
            if date.fromisoformat(end_date_str) < today:
                return False
        except ValueError:
            return False

    return True


def push_version_notification(items):
    try:
        release_res = requests.get(settings.LATEST_RELEASE_URL, timeout=5)
        release_res.raise_for_status()
        tag = release_res.json().get("tag_name", "").lstrip("v")
        print(f"Latest release version: {tag}, installed version: {actual_version}")

        if settings.ADVERTISE_LATEST_VERSION and not is_last_version(actual_version, tag):
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
                    "more_info_link": "https://github.com/numerique-gouv/sites-faciles/releases",
                },
            )
        return items
    except Exception:
        return items


def get_all_notifications():
    cached = cache.get(settings.INFORMATION_CACHE_KEY)
    if cached is not None:
        return cached

    items = []
    items = push_version_notification(items)

    try:
        res = requests.get(settings.INFORMATION_URL, timeout=5)
        res.raise_for_status()
        data = res.json()
    except Exception:
        data = {}

    for item in data.get("items", []):
        if is_displayable_notification(item):
            items.append(item)

    cache.set(settings.INFORMATION_CACHE_KEY, items, settings.INFORMATION_CACHE_TIMEOUT)
    return items
