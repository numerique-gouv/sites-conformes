import logging
from datetime import date

import requests
from django.conf import settings
from django.core.cache import cache
from packaging.version import Version

from sites_conformes import __version__ as current_version

logger = logging.getLogger(__name__)

VALID_TYPES = ["info", "warning", "alert"]
REQUIRED_FIELDS = ["type", "title", "start_date"]

NOTIFICATIONS_CACHE_KEY = "sf_notifications"
NOTIFICATIONS_CACHE_TIMEOUT = 60 * 60


def is_up_to_date(installed_version, latest_version):
    return Version(installed_version) >= Version(latest_version)


def is_valid_notification(item):
    """Vérifie qu'une notification est bien formée (champs requis et type valide)."""
    for field in REQUIRED_FIELDS:
        if not item.get(field):
            return False

    if item.get("type") not in VALID_TYPES:
        return False

    return True


def should_display_notification(item):
    """Vérifie qu'une notification valide est affichable aujourd'hui (fenêtre de dates)."""
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


def fetch_latest_version():
    """Récupère la dernière version publiée sur GitHub, ou None en cas d'erreur (loggée)."""
    try:
        release_res = requests.get(settings.LATEST_RELEASE_URL, timeout=5)
        release_res.raise_for_status()
        return release_res.json().get("tag_name", "").lstrip("v")
    except Exception as e:
        logger.warning("Impossible de récupérer la dernière version depuis %s : %s", settings.LATEST_RELEASE_URL, e)
        return None


def push_version_notification(items):
    """Ajoute en tête une notification si une version plus récente est disponible."""
    if not settings.ADVERTISE_LATEST_VERSION or not current_version:
        return items

    latest_version = fetch_latest_version()
    if not latest_version:
        return items

    if not is_up_to_date(current_version, latest_version):
        items.insert(
            0,
            {
                "type": "info",
                "title": f"Une nouvelle version de Sites Conformes est disponible ({latest_version})",
                "description": (
                    f"Vous utilisez une version obsolète"
                    f"{f' ({current_version})' if current_version else ''}. "
                    "Rapprochez-vous de la personne qui a installé votre site "
                    "pour réaliser la mise à jour."
                ),
                "more_info_link": settings.RELEASES_URL,
            },
        )
    return items


def fetch_notifications():
    """Récupère les notifications depuis le fichier distant, ou une liste vide en cas d'erreur (loggée)."""
    try:
        res = requests.get(settings.NOTIFICATIONS_FILE_URL, timeout=5)
        res.raise_for_status()
        return res.json().get("items", [])
    except Exception as e:
        logger.warning("Impossible de récupérer les notifications depuis %s : %s", settings.NOTIFICATIONS_FILE_URL, e)
        return []


def get_all_notifications():
    cached = cache.get(NOTIFICATIONS_CACHE_KEY)
    if cached is not None:
        return cached

    items = []
    items = push_version_notification(items)

    for item in fetch_notifications():
        if is_valid_notification(item) and should_display_notification(item):
            items.append(item)

    cache.set(NOTIFICATIONS_CACHE_KEY, items, NOTIFICATIONS_CACHE_TIMEOUT)
    return items
