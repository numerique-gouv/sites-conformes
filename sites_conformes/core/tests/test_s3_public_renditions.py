import os
import runpy
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase
from storages.backends.s3 import S3Storage

S3_ENV = {
    "S3_HOST": "s3.example.com",
    "S3_BUCKET_NAME": "bucket",
    "S3_KEY_ID": "key-id",
    "S3_KEY_SECRET": "key-secret",
}


def load_settings(**env):
    """Run config/settings.py in an isolated namespace, with only the given S3_* environment variables."""
    base = {key: value for key, value in os.environ.items() if not key.startswith("S3_")}
    with patch.dict(os.environ, {**base, **env}, clear=True):
        return runpy.run_path(str(settings.BASE_DIR / "config" / "settings.py"))


def build_storage(storage_settings):
    return S3Storage(**storage_settings["OPTIONS"])


class S3PublicRenditionsSettingsTestCase(SimpleTestCase):
    def test_disabled_by_default(self):
        loaded = load_settings(**S3_ENV)

        self.assertNotIn("renditions", loaded["STORAGES"])
        self.assertNotIn("WAGTAILIMAGES_RENDITION_STORAGE", loaded)

    def test_ignored_without_s3(self):
        loaded = load_settings(S3_PUBLIC_RENDITIONS="1")

        self.assertNotIn("renditions", loaded["STORAGES"])
        self.assertNotIn("WAGTAILIMAGES_RENDITION_STORAGE", loaded)

    def test_enabled_uses_a_dedicated_public_storage(self):
        loaded = load_settings(**S3_ENV, S3_PUBLIC_RENDITIONS="true")

        self.assertEqual(loaded["WAGTAILIMAGES_RENDITION_STORAGE"], "renditions")
        renditions = build_storage(loaded["STORAGES"]["renditions"])
        self.assertEqual(renditions.default_acl, "public-read")
        self.assertFalse(renditions.querystring_auth)
        self.assertEqual(renditions.bucket_name, "bucket")

    def test_enabled_leaves_default_storage_private_and_signed(self):
        loaded = load_settings(**S3_ENV, S3_PUBLIC_RENDITIONS="true")

        default = build_storage(loaded["STORAGES"]["default"])
        self.assertIsNone(default.default_acl)
        self.assertTrue(default.querystring_auth)
        self.assertIn("X-Amz-Signature=", default.url("documents/report.pdf"))

    def test_enabled_rendition_urls_are_unsigned(self):
        loaded = load_settings(**S3_ENV, S3_PUBLIC_RENDITIONS="true")

        url = build_storage(loaded["STORAGES"]["renditions"]).url("images/logo.2e16d0ba.fill-1200x630.png")

        self.assertTrue(url.startswith("https://s3.example.com/bucket/images/logo.2e16d0ba.fill-1200x630.png"))
        self.assertNotIn("X-Amz-", url)
