import os
import tempfile

from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from wagtail.models import Page, Revision

from db_storage.models import StoredFile


class MigrateDbToFilesCommandTestCase(TestCase):
    """Tests for the migrate_db_to_files management command."""

    def _make_stored_file(self, name="images/photo.jpg", content=b"\xff\xd8\xff\xe0"):
        return StoredFile.objects.create(
            name=name,
            content=content,
            content_type="image/jpeg",
            size=len(content),
        )

    def test_fails_without_media_root(self):
        with override_settings(MEDIA_ROOT=""):
            with self.assertRaises(CommandError):
                call_command("migrate_db_to_files", "--skip-urls")

    def test_dry_run_does_not_write_files(self):
        with tempfile.TemporaryDirectory() as media_root:
            self._make_stored_file()
            with override_settings(MEDIA_ROOT=media_root):
                call_command("migrate_db_to_files", "--dry-run", "--skip-urls")

            dest = os.path.join(media_root, "images", "photo.jpg")
            self.assertFalse(os.path.exists(dest))

    def test_writes_file_to_filesystem(self):
        with tempfile.TemporaryDirectory() as media_root:
            self._make_stored_file(content=b"hello")
            with override_settings(MEDIA_ROOT=media_root):
                call_command("migrate_db_to_files", "--skip-urls")

            dest = os.path.join(media_root, "images", "photo.jpg")
            self.assertTrue(os.path.exists(dest))
            with open(dest, "rb") as f:
                self.assertEqual(f.read(), b"hello")

    def test_creates_subdirectories(self):
        with tempfile.TemporaryDirectory() as media_root:
            self._make_stored_file(name="a/b/c/deep.png", content=b"data")
            with override_settings(MEDIA_ROOT=media_root):
                call_command("migrate_db_to_files", "--skip-urls")

            dest = os.path.join(media_root, "a", "b", "c", "deep.png")
            self.assertTrue(os.path.exists(dest))

    def test_skips_existing_files(self):
        with tempfile.TemporaryDirectory() as media_root:
            dest_dir = os.path.join(media_root, "images")
            os.makedirs(dest_dir)
            dest = os.path.join(dest_dir, "photo.jpg")
            with open(dest, "wb") as f:
                f.write(b"original")

            self._make_stored_file(content=b"new-content")
            with override_settings(MEDIA_ROOT=media_root):
                call_command("migrate_db_to_files", "--skip-urls")

            with open(dest, "rb") as f:
                self.assertEqual(f.read(), b"original")

    def test_empty_db(self):
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                call_command("migrate_db_to_files", "--skip-urls")

    def test_update_revision_urls(self):
        root_page = Page.objects.first()
        ct = ContentType.objects.get_for_model(Page)
        revision = Revision.objects.create(
            content_type=ct,
            base_content_type=ct,
            object_id=str(root_page.pk),
            content={
                "title": "Test",
                "image": "/db-storage/serve?name=images/pic.jpg",
            },
        )

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root, MEDIA_URL="/media/"):
                call_command("migrate_db_to_files", "--skip-files")

        revision.refresh_from_db()
        self.assertNotIn("/db-storage/serve?name=", str(revision.content))
        self.assertEqual(revision.content["image"], "/media/images/pic.jpg")

    def test_dry_run_does_not_update_revision_urls(self):
        root_page = Page.objects.first()
        ct = ContentType.objects.get_for_model(Page)
        revision = Revision.objects.create(
            content_type=ct,
            base_content_type=ct,
            object_id=str(root_page.pk),
            content={
                "image": "/db-storage/serve?name=images/pic.jpg",
            },
        )

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root, MEDIA_URL="/media/"):
                call_command("migrate_db_to_files", "--dry-run", "--skip-files")

        revision.refresh_from_db()
        self.assertIn("/db-storage/serve?name=", revision.content["image"])
