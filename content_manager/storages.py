"""
S3 storage that makes Wagtail images publicly readable, object by object.

OVHcloud Object Storage does not support bucket policies, and a ``public-read``
ACL on the bucket would also allow listing it. Instead, each image object gets a
``public-read`` ACL while the bucket itself stays private.

Documents are kept private on purpose: Wagtail applies collection view
restrictions to them, so they must only be reachable through the Wagtail serve
view (``WAGTAILDOCS_SERVE_METHOD = "serve_view"``), never through a public URL.
Wagtail does not apply any front-end restriction to images.
"""

from storages.backends.s3 import S3Storage

# Upload prefixes of Wagtail original images and renditions.
PUBLIC_PREFIXES = ("original_images/", "images/")
PUBLIC_ACL = "public-read"


def is_public_key(key: str, location: str = "") -> bool:
    """Return True if the object key (including the storage location) is a public image."""
    location = location.strip("/")
    if location:
        prefix = f"{location}/"
        if not key.startswith(prefix):
            return False
        key = key[len(prefix) :]
    return key.startswith(PUBLIC_PREFIXES)


class PublicImagesS3Storage(S3Storage):
    def get_object_parameters(self, name):
        # name is the full object key, location included.
        params = super().get_object_parameters(name)
        if is_public_key(name, self.location):
            params["ACL"] = PUBLIC_ACL
        return params
