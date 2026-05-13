import os
import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings

from db_storage.models import StoredFile


class MigrateFilesToDbCommandTestCase(TestCase):
    """Tests for the migrate_files_to_db management command."""

    def _write_file(self, base_dir, relative_path, content=b"data"):
        full_path = os.path.join(base_dir, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(content)
        return full_path

    def test_invalid_media_root_writes_error(self):
        with override_settings(MEDIA_ROOT="/nonexistent/path"):
            _out = self.run_command()
        self.assertEqual(StoredFile.objects.count(), 0)

    def run_command(self, *args, **kwargs):
        from io import StringIO

        out = StringIO()
        call_command("migrate_files_to_db", *args, stdout=out, **kwargs)
        return out.getvalue()

    def test_dry_run_does_not_create_stored_files(self):
        with tempfile.TemporaryDirectory() as media_root:
            self._write_file(media_root, "images/photo.jpg", b"\xff\xd8\xff\xe0")
            with override_settings(MEDIA_ROOT=media_root):
                self.run_command("--dry-run")

        self.assertEqual(StoredFile.objects.count(), 0)

    def test_migrates_file_to_db(self):
        with tempfile.TemporaryDirectory() as media_root:
            self._write_file(media_root, "images/photo.jpg", b"\xff\xd8\xff\xe0")
            with override_settings(MEDIA_ROOT=media_root):
                self.run_command()

        self.assertEqual(StoredFile.objects.count(), 1)
        stored = StoredFile.objects.first()
        self.assertEqual(stored.name, "images/photo.jpg")
        self.assertEqual(bytes(stored.content), b"\xff\xd8\xff\xe0")
        self.assertEqual(stored.size, 4)

    def test_guesses_content_type(self):
        with tempfile.TemporaryDirectory() as media_root:
            self._write_file(media_root, "docs/file.pdf", b"%PDF")
            with override_settings(MEDIA_ROOT=media_root):
                self.run_command()

        stored = StoredFile.objects.first()
        self.assertEqual(stored.content_type, "application/pdf")

    def test_unknown_content_type_falls_back_to_octet_stream(self):
        with tempfile.TemporaryDirectory() as media_root:
            self._write_file(media_root, "data/file.bin", b"\x00\x01")
            with override_settings(MEDIA_ROOT=media_root):
                self.run_command()

        stored = StoredFile.objects.first()
        self.assertEqual(stored.content_type, "application/octet-stream")

    def test_skips_existing_stored_files(self):
        StoredFile.objects.create(
            name="images/photo.jpg",
            content=b"old",
            content_type="image/jpeg",
            size=3,
        )

        with tempfile.TemporaryDirectory() as media_root:
            self._write_file(media_root, "images/photo.jpg", b"new")
            with override_settings(MEDIA_ROOT=media_root):
                self.run_command()

        self.assertEqual(StoredFile.objects.count(), 1)
        self.assertEqual(bytes(StoredFile.objects.first().content), b"old")

    def test_migrates_nested_files_with_relative_paths(self):
        with tempfile.TemporaryDirectory() as media_root:
            self._write_file(media_root, "a/b/c/deep.png", b"deep")
            with override_settings(MEDIA_ROOT=media_root):
                self.run_command()

        stored = StoredFile.objects.first()
        self.assertEqual(stored.name, "a/b/c/deep.png")

    def test_migrates_multiple_files(self):
        with tempfile.TemporaryDirectory() as media_root:
            self._write_file(media_root, "images/a.jpg", b"aaa")
            self._write_file(media_root, "images/b.jpg", b"bbb")
            self._write_file(media_root, "docs/c.pdf", b"ccc")
            with override_settings(MEDIA_ROOT=media_root):
                self.run_command()

        self.assertEqual(StoredFile.objects.count(), 3)

    def test_empty_media_root(self):
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self.run_command()

        self.assertEqual(StoredFile.objects.count(), 0)
