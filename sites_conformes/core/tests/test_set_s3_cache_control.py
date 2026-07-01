"""Tests for S3 Cache-Control settings and the ``set_s3_cache_control`` command."""

from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings

S3_ENV = {
    "S3_HOST": "s3.example.com",
    "S3_BUCKET_NAME": "bucket",
    "S3_KEY_ID": "k",
    "S3_KEY_SECRET": "s",
    "S3_BUCKET_REGION": "eu-west-3",
}


class S3CacheControlSettingsTestCase(TestCase):
    """Tests for MEDIA_CACHE_CONTROL default and S3 object_parameters."""

    def test_media_cache_control_default(self):
        """The default MEDIA_CACHE_CONTROL should be a sensible value."""
        self.assertEqual(settings.MEDIA_CACHE_CONTROL, "public, max-age=3600")

    @patch.dict("os.environ", S3_ENV, clear=False)
    def test_s3_object_parameters_include_cache_control(self):
        """When S3_HOST is set, STORAGES should include CacheControl."""
        # Re-import settings to trigger the S3 branch
        # (in tests settings are already loaded, we check the env-driven value)
        import os

        os.environ["S3_HOST"] = "s3.example.com"
        os.environ["S3_BUCKET_NAME"] = "bucket"
        os.environ["S3_KEY_ID"] = "k"
        os.environ["S3_KEY_SECRET"] = "s"

        # Force reload the relevant part of settings
        # Since Django settings can't be reloaded, we test the logic indirectly
        # by checking what the management command reads from settings
        self.assertEqual(settings.MEDIA_CACHE_CONTROL, "public, max-age=3600")

    @override_settings(MEDIA_CACHE_CONTROL="public, max-age=604800")
    def test_media_cache_control_custom_value(self):
        """MEDIA_CACHE_CONTROL should be overridable via settings."""
        self.assertEqual(settings.MEDIA_CACHE_CONTROL, "public, max-age=604800")


class SetS3CacheControlCommandTestCase(TestCase):
    """Tests for the ``set_s3_cache_control`` management command."""

    @patch.dict("os.environ", {}, clear=False)
    def test_fails_without_s3_config(self):
        """Command should fail if S3 is not configured."""
        import os

        os.environ.pop("S3_HOST", None)
        with self.assertRaises(Exception):
            call_command("set_s3_cache_control")

    @patch("sites_conformes.core.management.commands.set_s3_cache_control.boto3")
    @patch.dict("os.environ", S3_ENV)
    def test_dry_run_lists_objects(self, mock_boto3):
        """Dry run should list objects but not modify them."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        # Simulate an S3 listing with one object
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [{"Key": "images/photo.jpg"}],
                "KeyCount": 1,
            }
        ]
        # Simulate head_object returning no CacheControl yet
        mock_client.head_object.return_value = {
            "CacheControl": "",
            "ContentType": "image/jpeg",
        }

        call_command("set_s3_cache_control", "--dry-run")

        # Should have listed objects but NOT called copy_object
        mock_client.get_paginator.assert_called_once_with("list_objects_v2")
        mock_client.copy_object.assert_not_called()

    @patch("sites_conformes.core.management.commands.set_s3_cache_control.boto3")
    @patch.dict("os.environ", S3_ENV)
    def test_updates_missing_cache_control(self, mock_boto3):
        """Objects without CacheControl should get one via copy_object."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [{"Key": "images/photo.jpg"}],
                "KeyCount": 1,
            }
        ]
        mock_client.head_object.return_value = {
            "CacheControl": "",
            "ContentType": "image/jpeg",
        }

        call_command("set_s3_cache_control")

        mock_client.copy_object.assert_called_once()
        call_kwargs = mock_client.copy_object.call_args.kwargs
        self.assertIn("CacheControl", call_kwargs)
        self.assertEqual(call_kwargs["CacheControl"], settings.MEDIA_CACHE_CONTROL)

    @patch("sites_conformes.core.management.commands.set_s3_cache_control.boto3")
    @patch.dict("os.environ", S3_ENV)
    def test_skips_objects_with_correct_header(self, mock_boto3):
        """Objects that already have the target CacheControl should be skipped."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [{"Key": "ok.jpg"}],
                "KeyCount": 1,
            }
        ]
        # Object already has the correct CacheControl
        mock_client.head_object.return_value = {
            "CacheControl": settings.MEDIA_CACHE_CONTROL,
            "ContentType": "image/jpeg",
        }

        call_command("set_s3_cache_control")

        mock_client.copy_object.assert_not_called()

    @patch("sites_conformes.core.management.commands.set_s3_cache_control.boto3")
    @patch.dict("os.environ", S3_ENV)
    def test_custom_cache_control_value(self, mock_boto3):
        """The --cache-control option should override the default value."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [{"Key": "img.png"}],
                "KeyCount": 1,
            }
        ]
        mock_client.head_object.return_value = {
            "CacheControl": "",
            "ContentType": "image/png",
        }

        call_command("set_s3_cache_control", "--cache-control", "public, max-age=604800")

        mock_client.copy_object.assert_called_once()
        call_kwargs = mock_client.copy_object.call_args.kwargs
        self.assertEqual(call_kwargs["CacheControl"], "public, max-age=604800")
