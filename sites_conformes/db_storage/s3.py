from django.conf import settings

S3_BACKENDS = {
    "storages.backends.s3.S3Storage",
    "storages.backends.s3boto3.S3Boto3Storage",
}


def get_s3_config() -> dict | None:
    """Return the S3 connection settings of the default storage, or ``None`` if it isn't S3.

    The migration commands read the configuration from ``settings.STORAGES["default"]``
    (built from the ``S3_*`` environment variables in ``config/settings.py``), so they
    always target the same bucket as the site.
    """
    storage = settings.STORAGES.get("default", {})
    if storage.get("BACKEND") not in S3_BACKENDS:
        return None

    options = storage.get("OPTIONS", {})
    return {
        "endpoint_url": options.get("endpoint_url"),
        "bucket_name": options.get("bucket_name", ""),
        "access_key": options.get("access_key", ""),
        "secret_key": options.get("secret_key", ""),
        "region_name": options.get("region_name", "fr"),
        "location": options.get("location", ""),
    }
