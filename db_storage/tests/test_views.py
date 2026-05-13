from django.test import TestCase

from db_storage.models import StoredFile


class ServeFileViewTestCase(TestCase):
    def test_serve_existing_file(self):
        StoredFile.objects.create(
            name="test/hello.txt",
            content=b"hello world",
            content_type="text/plain",
            size=11,
        )
        response = self.client.get("/db-storage/serve/?name=test/hello.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"hello world")
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertEqual(response["Content-Length"], "11")

    def test_serve_missing_file(self):
        response = self.client.get("/db-storage/serve/?name=nonexistent.txt")
        self.assertEqual(response.status_code, 404)

    def test_serve_no_name_param(self):
        response = self.client.get("/db-storage/serve/")
        self.assertEqual(response.status_code, 404)

    def test_serve_cache_headers(self):
        StoredFile.objects.create(
            name="cached.png",
            content=b"\x89PNG",
            content_type="image/png",
            size=4,
        )
        response = self.client.get("/db-storage/serve/?name=cached.png")
        self.assertEqual(response["Cache-Control"], "public, max-age=3600")
