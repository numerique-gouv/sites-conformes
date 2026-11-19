"""Import d'images distantes dans la médiathèque Wagtail.

Les photos et captures sont copiées dans la médiathèque du site (stockage S3) :
les visiteurs ne chargent rien depuis GitHub ou beta.gouv.fr, et le site ne
dépend pas de la disponibilité de ces services.
"""

import hashlib
import logging
import urllib.request
from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import urlparse

from django.contrib.staticfiles import finders
from django.core.files.images import ImageFile
from wagtail.images import get_image_model
from wagtail.models import Collection

from fabrique.models import ImageImportee

logger = logging.getLogger(__name__)

COLLECTION_NAME = "beta.gouv.fr"
MAX_BYTES = 8 * 1024 * 1024
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _collection() -> Collection:
    root = Collection.get_first_root_node()
    existing = root.get_children().filter(name=COLLECTION_NAME).first()
    return existing or root.add_child(name=COLLECTION_NAME)


def download(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "fabrique-site-facile/sync"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError(f"image trop lourde ({url})")
    return data


def import_image(url: str, title: str, downloader=download):
    """Renvoie l'image Wagtail correspondant à l'adresse, téléchargée si besoin. None en cas d'échec."""
    if not url:
        return None
    known = ImageImportee.objects.select_related("image").filter(url=url).first()
    try:
        data = downloader(url)
    except Exception as e:  # noqa: BLE001
        logger.warning("Image %s inaccessible : %s", url, e)
        return known.image if known else None

    digest = hashlib.sha256(data).hexdigest()
    if known and known.empreinte == digest:
        return known.image

    suffix = PurePosixPath(urlparse(url).path).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        suffix = ".jpg"
    filename = f"{PurePosixPath(urlparse(url).path).parent.name or 'image'}{suffix}"
    try:
        image = get_image_model()(title=title, collection=_collection(), file=ImageFile(BytesIO(data), name=filename))
        image.save()
    except Exception as e:  # noqa: BLE001 (fichier qui n'est pas une image valide)
        logger.warning("Image %s illisible : %s", url, e)
        return known.image if known else None

    if known:
        old = known.image
        known.image, known.empreinte = image, digest
        known.save()
        old.delete()
    else:
        ImageImportee.objects.create(url=url, empreinte=digest, image=image)
    return image


DEFAULT_AVATAR_STATIC = "fabrique/avatar-defaut.png"


def default_avatar():
    """Pictogramme de la Fabrique, utilisé pour les membres sans photo (copié une fois dans la médiathèque)."""
    path = finders.find(DEFAULT_AVATAR_STATIC)
    if not path:
        return None
    with open(path, "rb") as f:
        data = f.read()
    return import_image(
        f"static:{DEFAULT_AVATAR_STATIC}", "Membre sans photo — pictogramme de la Fabrique", downloader=lambda _: data
    )
