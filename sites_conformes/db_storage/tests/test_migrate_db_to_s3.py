from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase

from db_storage.models import StoredFile

S3_ENV = {
    "S3_HOST": "s3.example.com",
    "S3_BUCKET_NAME": "bucket",
    "S3_KEY_ID": "k",
    "S3_KEY_SECRET": "s",
    "S3_LOCATION": "media",
}


class MigrateDbToS3CommandTestCase(TestCase):
    """Tests for the migrate_db_to_s3 management command."""

    @patch.dict("os.environ", {}, clear=False)
    def test_fails_without_s3_config(self):
        """Command should fail if S3 is not configured."""
        import os

        os.environ.pop("S3_HOST", None)
        with self.assertRaises(Exception):
            call_command("migrate_db_to_s3")

    @patch("db_storage.management.commands.migrate_db_to_s3.boto3")
    @patch.dict("os.environ", S3_ENV)
    def test_dry_run_does_not_upload(self, mock_boto3):
        """Dry run should not upload any files to S3."""
        StoredFile.objects.create(
            name="images/photo.jpg",
            content=b"\xff\xd8\xff\xe0",
            content_type="image/jpeg",
            size=4,
        )

        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        call_command("migrate_db_to_s3", "--dry-run")

        mock_client.put_object.assert_not_called()

    @patch("db_storage.management.commands.migrate_db_to_s3.boto3")
    @patch.dict("os.environ", S3_ENV)
    def test_upload_files(self, mock_boto3):
        """Files should be uploaded from StoredFile to S3."""
        StoredFile.objects.create(
            name="images/photo.jpg",
            content=b"\xff\xd8\xff\xe0",
            content_type="image/jpeg",
            size=4,
        )

        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        # Simulate file not existing on S3
        error_response = {"Error": {"Code": "404"}}
        mock_client.exceptions.ClientError = type("ClientError", (Exception,), {})
        mock_client.head_object.side_effect = mock_client.exceptions.ClientError(error_response, "HeadObject")

        call_command("migrate_db_to_s3")

        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args[1]
        self.assertEqual(call_kwargs["Bucket"], "bucket")
        self.assertEqual(call_kwargs["Key"], "media/images/photo.jpg")
        self.assertEqual(call_kwargs["ContentType"], "image/jpeg")

    @patch("db_storage.management.commands.migrate_db_to_s3.boto3")
    @patch.dict("os.environ", S3_ENV)
    def test_skip_existing_on_s3(self, mock_boto3):
        """Files already on S3 should be skipped."""
        StoredFile.objects.create(
            name="images/existing.jpg",
            content=b"\xff\xd8\xff\xe0",
            content_type="image/jpeg",
            size=4,
        )

        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        # Simulate file already exists on S3
        mock_client.head_object.return_value = {"ContentLength": 4}

        call_command("migrate_db_to_s3")

        mock_client.put_object.assert_not_called()

    @patch("db_storage.management.commands.migrate_db_to_s3.boto3")
    @patch.dict("os.environ", S3_ENV)
    def test_empty_db(self, mock_boto3):
        """No error when database has no stored files."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        call_command("migrate_db_to_s3")

        mock_client.put_object.assert_not_called()
