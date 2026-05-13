from django.core.files.base import ContentFile
from django.test import TestCase

from db_storage.models import StoredFile
from db_storage.storage import DatabaseStorage


class DatabaseStorageTestCase(TestCase):
    def setUp(self):
        self.storage = DatabaseStorage()

    def test_save_and_open(self):
        content = ContentFile(b"hello world")
        name = self.storage.save("test/hello.txt", content)
        self.assertEqual(name, "test/hello.txt")

        f = self.storage.open("test/hello.txt")
        self.assertEqual(f.read(), b"hello world")

    def test_exists(self):
        self.assertFalse(self.storage.exists("nonexistent.txt"))
        self.storage.save("exists.txt", ContentFile(b"data"))
        self.assertTrue(self.storage.exists("exists.txt"))

    def test_delete(self):
        self.storage.save("to_delete.txt", ContentFile(b"data"))
        self.assertTrue(self.storage.exists("to_delete.txt"))
        self.storage.delete("to_delete.txt")
        self.assertFalse(self.storage.exists("to_delete.txt"))

    def test_size(self):
        self.storage.save("sized.txt", ContentFile(b"12345"))
        self.assertEqual(self.storage.size("sized.txt"), 5)

    def test_listdir(self):
        self.storage.save("dir/file1.txt", ContentFile(b"a"))
        self.storage.save("dir/file2.txt", ContentFile(b"b"))
        self.storage.save("dir/sub/file3.txt", ContentFile(b"c"))
        dirs, files = self.storage.listdir("dir")
        self.assertIn("sub", dirs)
        self.assertIn("file1.txt", files)
        self.assertIn("file2.txt", files)

    def test_url(self):
        url = self.storage.url("test/image.jpg")
        self.assertIn("serve", url)
        self.assertIn("name=test/image.jpg", url)

    def test_get_available_name(self):
        self.storage.save("conflict.txt", ContentFile(b"first"))
        new_name = self.storage.get_available_name("conflict.txt")
        self.assertEqual(new_name, "conflict_1.txt")

    def test_content_type_guessed(self):
        self.storage.save("photo.jpg", ContentFile(b"\xff\xd8\xff"))
        stored = StoredFile.objects.get(name="photo.jpg")
        self.assertEqual(stored.content_type, "image/jpeg")

    def test_overwrite_on_same_name(self):
        self.storage._save("same.txt", ContentFile(b"version1"))
        self.storage._save("same.txt", ContentFile(b"version2"))
        f = self.storage.open("same.txt")
        self.assertEqual(f.read(), b"version2")
