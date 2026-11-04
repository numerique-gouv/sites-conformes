"""
Integration tests for S3 Cache-Control that require a running Garage cluster.

These tests are skipped unless the ``GARAGE_INTEGRATION_TESTS`` environment
variable is set to ``1`` and Garage is reachable at ``localhost:3900``.

Usage::

    # Start Garage first
    docker compose up -d garage

    # Run these tests
    GARAGE_INTEGRATION_TESTS=1 uv run python3 manage.py test \\
        sites_conformes.core.tests.test_s3_integration \\
        --settings=config.settings_test -v2
"""

import os
from unittest import skipUnless

import boto3
from botocore.config import Config
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase
from dotenv import load_dotenv

load_dotenv(override=True)

GARAGE_AVAILABLE = os.environ.get("GARAGE_INTEGRATION_TESTS") == "1"


def _garage_client():
    """Return a boto3 client pointing at the local Garage cluster."""
    return boto3.client(
        "s3",
        endpoint_url="http://localhost:3900",
        aws_access_key_id=os.getenv("S3_KEY_ID", "GKarag..."),
        aws_secret_access_key=os.getenv("S3_KEY_SECRET", ""),
        region_name=os.getenv("S3_BUCKET_REGION", "fr"),
        config=Config(signature_version="s3v4"),
    )


@skipUnless(GARAGE_AVAILABLE, "Set GARAGE_INTEGRATION_TESTS=1 and start Garage")
class S3CacheControlIntegrationTestCase(TestCase):
    """Verify Cache-Control headers on objects uploaded to Garage via django-storages.

    Prerequisites:
        - Garage container running (``docker compose up -d garage``)
        - ``GARAGE_INTEGRATION_TESTS=1`` in the environment
        - ``.env`` configured with Garage credentials
    """

    def setUp(self):
        self.client = _garage_client()
        self.bucket = os.getenv("S3_BUCKET_NAME", "sites-conformes-media")

    def tearDown(self):
        # Clean up test objects after each test
        for key in [
            "integration-test.txt",
            "integration-test-0.txt",
            "integration-test-1.txt",
            "integration-test-2.txt",
        ]:
            try:
                self.client.delete_object(Bucket=self.bucket, Key=key)
            except Exception:
                pass

    def test_garage_is_reachable(self):
        """Sanity check: Garage should respond on the S3 API port."""
        response = self.client.list_buckets()
        names = [b["Name"] for b in response["Buckets"]]
        self.assertIn(self.bucket, names)

    def test_default_storage_uploads_with_cache_control(self):
        """``default_storage.save`` should set CacheControl on the uploaded object."""
        path = default_storage.save("integration-test.txt", ContentFile(b"cache-control-test"))

        head = self.client.head_object(Bucket=self.bucket, Key=path)
        self.assertIn("CacheControl", head)
        self.assertEqual(head["CacheControl"], settings.MEDIA_CACHE_CONTROL)

    def test_cache_control_is_present_on_all_media_uploads(self):
        """Multiple uploads should all carry the CacheControl header."""
        for i in range(3):
            key = f"integration-test-{i}.txt"
            path = default_storage.save(key, ContentFile(f"file-{i}".encode()))

            head = self.client.head_object(Bucket=self.bucket, Key=path)
            self.assertIn("CacheControl", head)
            self.assertEqual(head["CacheControl"], settings.MEDIA_CACHE_CONTROL)

    def test_cache_control_persists_on_read(self):
        """The CacheControl header set at upload time should be preserved when reading back."""
        path = default_storage.save("integration-test.txt", ContentFile(b"persist-check"))

        # Read back via boto3 to verify the header is persistent
        obj = self.client.get_object(Bucket=self.bucket, Key=path)
        self.assertEqual(obj["CacheControl"], settings.MEDIA_CACHE_CONTROL)
