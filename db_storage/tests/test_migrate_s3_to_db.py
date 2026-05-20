from unittest.mock import MagicMock, patch

from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from wagtail.models import Page, Revision

from db_storage.models import StoredFile

S3_ENV = {
    "S3_HOST": "s3.example.com",
    "S3_BUCKET_NAME": "bucket",
    "S3_KEY_ID": "k",
    "S3_KEY_SECRET": "s",
    "S3_LOCATION": "media",
}


class MigrateS3ToDbCommandTestCase(TestCase):
    """Tests for the migrate_s3_to_db management command."""

    def _mock_s3_env(self):
        return {
            "S3_HOST": "s3.example.com",
            "S3_PROTOCOL": "https",
            "S3_BUCKET_NAME": "test-bucket",
            "S3_KEY_ID": "test-key",
            "S3_KEY_SECRET": "test-secret",
            "S3_BUCKET_REGION": "eu-west-3",
            "S3_LOCATION": "media",
        }

    @patch.dict("os.environ", {}, clear=False)
    def test_fails_without_s3_config(self):
        """Command should fail if S3 is not configured."""
        # Remove S3_HOST if present
        import os

        os.environ.pop("S3_HOST", None)
        with self.assertRaises(Exception):
            call_command("migrate_s3_to_db", "--skip-urls")

    @patch("db_storage.management.commands.migrate_s3_to_db.boto3")
    @patch.dict("os.environ", S3_ENV)
    def test_transfer_files_dry_run(self, mock_boto3):
        """Dry run should not create StoredFile entries."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "media/images/photo.jpg", "Size": 1024},
                    {"Key": "media/documents/doc.pdf", "Size": 2048},
                ]
            }
        ]

        call_command("migrate_s3_to_db", "--dry-run", "--skip-urls")

        self.assertEqual(StoredFile.objects.count(), 0)

    @patch("db_storage.management.commands.migrate_s3_to_db.boto3")
    @patch.dict("os.environ", S3_ENV)
    def test_transfer_files(self, mock_boto3):
        """Files should be transferred from S3 to StoredFile."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "media/images/photo.jpg", "Size": 1024},
                ]
            }
        ]

        mock_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=b"\xff\xd8\xff\xe0")),
            "ContentType": "image/jpeg",
        }

        call_command("migrate_s3_to_db", "--skip-urls")

        self.assertEqual(StoredFile.objects.count(), 1)
        stored = StoredFile.objects.first()
        self.assertEqual(stored.name, "images/photo.jpg")
        self.assertEqual(stored.content_type, "image/jpeg")
        self.assertEqual(stored.size, 4)

    @patch("db_storage.management.commands.migrate_s3_to_db.boto3")
    @patch.dict("os.environ", S3_ENV)
    def test_skip_existing_files(self, mock_boto3):
        """Already existing StoredFile entries should be skipped."""
        StoredFile.objects.create(
            name="images/existing.jpg",
            content=b"old-data",
            content_type="image/jpeg",
            size=8,
        )

        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "media/images/existing.jpg", "Size": 1024},
                ]
            }
        ]

        call_command("migrate_s3_to_db", "--skip-urls")

        self.assertEqual(StoredFile.objects.count(), 1)
        stored = StoredFile.objects.first()
        self.assertEqual(bytes(stored.content), b"old-data")

    @patch("db_storage.management.commands.migrate_s3_to_db.boto3")
    @patch.dict("os.environ", S3_ENV)
    def test_update_revision_urls(self, mock_boto3):
        """S3 URLs in Revision.content (JSONField) should be replaced."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_paginator.return_value.paginate.return_value = []

        # Create a Revision with S3 URL in its content
        root_page = Page.objects.first()
        ct = ContentType.objects.get_for_model(Page)
        revision = Revision.objects.create(
            content_type=ct,
            base_content_type=ct,
            object_id=str(root_page.pk),
            content={
                "title": "Test",
                "image": "https://s3.example.com/bucket/media/images/pic.jpg",
            },
        )

        call_command("migrate_s3_to_db", "--skip-files")

        revision.refresh_from_db()
        self.assertNotIn("s3.example.com", str(revision.content))
        self.assertIn("/db-storage/serve?name=", revision.content["image"])
