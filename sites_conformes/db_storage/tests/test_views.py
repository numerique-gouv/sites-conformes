from django.test import TestCase, override_settings

from sites_conformes.db_storage.models import StoredFile


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


@override_settings(
    STORAGES={
        "default": {"BACKEND": "sites_conformes.db_storage.storage.DatabaseStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class ServeFileViewRestrictedDocumentTestCase(TestCase):
    """
    The db-storage serve endpoint must enforce the view restrictions of the collection
    of the Wagtail document backed by the requested file (YWH-PGM9363-59).
    """

    BODY = b"CONFIDENTIAL-RESTRICTED-DOCUMENT-BODY"

    def setUp(self):
        from django.core.files.base import ContentFile
        from wagtail.documents import get_document_model
        from wagtail.models import Collection

        root = Collection.get_first_root_node()
        self.public_collection = root.add_child(name="Public")
        self.restricted_collection = root.add_child(name="Restricted")

        Document = get_document_model()
        self.document = Document(title="Secret", collection=self.restricted_collection)
        self.document.file.save("secret.txt", ContentFile(self.BODY), save=True)
        self.url = f"/db-storage/serve/?name={self.document.file.name}"

    def restrict(self, restriction_type, **kwargs):
        from wagtail.models import CollectionViewRestriction

        return CollectionViewRestriction.objects.create(
            collection=self.restricted_collection, restriction_type=restriction_type, **kwargs
        )

    def test_unrestricted_document_is_served_publicly(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.BODY)
        self.assertEqual(response["Cache-Control"], "public, max-age=3600")

    def test_login_restricted_document_is_not_served_to_anonymous(self):
        from wagtail.models import CollectionViewRestriction

        self.restrict(CollectionViewRestriction.LOGIN)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(self.BODY, response.content)

    def test_login_restricted_document_is_served_to_logged_in_user(self):
        from django.contrib.auth import get_user_model
        from wagtail.models import CollectionViewRestriction

        self.restrict(CollectionViewRestriction.LOGIN)
        user = get_user_model().objects.create_user(username="reader", password="unused-test-password")
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.BODY)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_password_restricted_document_shows_password_form(self):
        from wagtail.models import CollectionViewRestriction

        self.restrict(CollectionViewRestriction.PASSWORD, password="test-password")
        response = self.client.get(self.url)
        self.assertNotIn(self.BODY, response.content)
        self.assertContains(response, 'name="password"')

    def test_password_restricted_document_is_served_once_password_passed(self):
        from wagtail.models import CollectionViewRestriction

        restriction = self.restrict(CollectionViewRestriction.PASSWORD, password="test-password")
        session = self.client.session
        session[CollectionViewRestriction.passed_view_restrictions_session_key] = [restriction.id]
        session.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.BODY)

    def test_restriction_on_parent_collection_applies(self):
        from wagtail.models import CollectionViewRestriction

        self.restrict(CollectionViewRestriction.LOGIN)
        child = self.restricted_collection.add_child(name="Child")
        self.document.collection = child
        self.document.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_security_headers(self):
        response = self.client.get(self.url)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("default-src 'none'", response["Content-Security-Policy"])
