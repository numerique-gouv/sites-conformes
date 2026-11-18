from io import StringIO
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from storages.backends.s3 import S3Storage
from wagtail.documents import get_document_model
from wagtail.images import get_image_model
from wagtail.models import Collection, CollectionViewRestriction

from content_manager.storages import PublicImagesS3Storage, is_public_key

COMMAND_MODULE = "content_manager.management.commands.set_s3_cache_control"
CACHE_CONTROL = "public, max-age=600"


def make_storage(**options):
    defaults = {
        "bucket_name": "bucket",
        "access_key": "key",
        "secret_key": "secret",
        "endpoint_url": "https://s3.example.org",
        "region_name": "gra",
    }
    defaults.update(options)
    return PublicImagesS3Storage(**defaults)


class IsPublicKeyTestCase(SimpleTestCase):
    def test_without_location(self):
        self.assertTrue(is_public_key("images/photo.width-800.jpg"))
        self.assertTrue(is_public_key("original_images/photo.jpg"))
        self.assertFalse(is_public_key("documents/report.pdf"))
        self.assertFalse(is_public_key("other/images/photo.jpg"))

    def test_with_location(self):
        self.assertTrue(is_public_key("site/images/photo.jpg", "site"))
        self.assertTrue(is_public_key("site/original_images/photo.jpg", "/site/"))
        self.assertFalse(is_public_key("site/documents/report.pdf", "site"))
        self.assertFalse(is_public_key("images/photo.jpg", "site"))


class PublicImagesS3StorageTestCase(SimpleTestCase):
    def test_images_get_public_acl(self):
        storage = make_storage(object_parameters={"CacheControl": CACHE_CONTROL})
        for name in ("images/photo.jpg", "original_images/photo.jpg"):
            params = storage._get_write_parameters(storage._normalize_name(name))
            self.assertEqual(params["ACL"], "public-read")
            self.assertEqual(params["CacheControl"], CACHE_CONTROL)

    def test_documents_stay_private(self):
        storage = make_storage(object_parameters={"CacheControl": CACHE_CONTROL})
        params = storage._get_write_parameters(storage._normalize_name("documents/report.pdf"))
        self.assertNotIn("ACL", params)
        self.assertEqual(params["CacheControl"], CACHE_CONTROL)

    def test_with_location(self):
        storage = make_storage(location="site")
        params = storage._get_write_parameters(storage._normalize_name("images/photo.jpg"))
        self.assertEqual(params["ACL"], "public-read")
        params = storage._get_write_parameters(storage._normalize_name("documents/report.pdf"))
        self.assertNotIn("ACL", params)

    def test_object_parameters_are_not_mutated(self):
        storage = make_storage(object_parameters={"CacheControl": CACHE_CONTROL})
        storage._get_write_parameters(storage._normalize_name("images/photo.jpg"))
        self.assertEqual(storage.object_parameters, {"CacheControl": CACHE_CONTROL})

    def test_public_urls_are_unsigned(self):
        storage = make_storage(
            location="site",
            custom_domain="s3.example.org/bucket",
            url_protocol="https:",
            querystring_auth=False,
        )
        url = storage.url("images/photo.jpg")
        self.assertEqual(url, "https://s3.example.org/bucket/site/images/photo.jpg")
        self.assertNotIn("X-Amz-Signature", url)


class SetS3CacheControlTestCase(TestCase):
    def setUp(self):
        self.client_mock = MagicMock()
        self.anonymous_mock = MagicMock()
        # Signed HEAD responses, by key. A missing key raises a 404.
        self.objects = {}
        # Keys readable by an anonymous HEAD request.
        self.public_keys = set()
        # Error code of a signed HEAD on a missing key (403 without s3:ListBucket).
        self.missing_code = "404"
        self.client_mock.head_object.side_effect = self._head
        self.anonymous_mock.head_object.side_effect = self._anonymous_head

    def _head(self, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": self.missing_code}}, "HeadObject")
        return self.objects[Key]

    def _anonymous_head(self, Bucket, Key):
        if Key not in self.public_keys:
            raise ClientError({"Error": {"Code": "403"}}, "HeadObject")
        return {}

    def _storage(self, cls=S3Storage, location=""):
        storage = MagicMock(spec=cls)
        storage.bucket_name = "bucket"
        storage.location = location
        storage.endpoint_url = "https://s3.example.org"
        storage.connection.meta.client = self.client_mock
        storage.unsigned_connection.meta.client = self.anonymous_mock
        storage._normalize_name.side_effect = lambda name: f"{location}/{name}" if location else name
        return storage

    def _call(self, storage, *args):
        out, err = StringIO(), StringIO()
        with patch(f"{COMMAND_MODULE}.default_storage", storage):
            call_command("set_s3_cache_control", "--cache-control", CACHE_CONTROL, *args, stdout=out, stderr=err)
        return out.getvalue()

    def _copied_keys(self):
        return {c.kwargs["Key"]: c.kwargs for c in self.client_mock.copy_object.call_args_list}

    def _create_image(self, name="photo.jpg"):
        return get_image_model().objects.create(title=name, file=f"original_images/{name}", width=100, height=100)

    def _create_rendition(self, image, name="photo.width-50.jpg"):
        return image.renditions.create(filter_spec="width-50", file=f"images/{name}", width=50, height=50)

    def _create_document(self, name="report.pdf"):
        return get_document_model().objects.create(title=name, file=f"documents/{name}")

    def test_requires_s3_storage(self):
        with patch(f"{COMMAND_MODULE}.default_storage", MagicMock()):
            with self.assertRaises(CommandError):
                call_command("set_s3_cache_control", stdout=StringIO())

    def test_keys_come_from_the_database(self):
        image = self._create_image()
        self._create_rendition(image)
        self._create_document()
        # Same file referenced twice: processed once.
        self._create_image()
        self.objects = {
            "site/original_images/photo.jpg": {},
            "site/images/photo.width-50.jpg": {},
            "site/documents/report.pdf": {},
            "site/images/orphan.jpg": {},
        }
        self._call(self._storage(location="site"))
        self.assertEqual(
            sorted(c.kwargs["Key"] for c in self.client_mock.copy_object.call_args_list),
            ["site/documents/report.pdf", "site/images/photo.width-50.jpg", "site/original_images/photo.jpg"],
        )
        self.client_mock.list_objects_v2.assert_not_called()
        self.client_mock.get_paginator.assert_not_called()
        self.client_mock.get_object_acl.assert_not_called()

    def test_dry_run_does_not_copy(self):
        self._create_image()
        self.objects = {"original_images/photo.jpg": {"ContentType": "image/jpeg"}}
        output = self._call(self._storage(), "--dry-run")
        self.client_mock.copy_object.assert_not_called()
        self.assertIn("[DRY RUN] Would update: original_images/photo.jpg", output)

    def test_updates_cache_control_and_keeps_metadata(self):
        self._create_document()
        self._create_image("up-to-date.jpg")
        self.objects = {
            "documents/report.pdf": {
                "ContentType": "application/pdf",
                "ContentDisposition": "attachment",
                "Metadata": {"foo": "bar"},
            },
            "original_images/up-to-date.jpg": {"ContentType": "image/jpeg", "CacheControl": CACHE_CONTROL},
        }
        self._call(self._storage())
        copied = self._copied_keys()
        self.assertEqual(set(copied), {"documents/report.pdf"})
        params = copied["documents/report.pdf"]
        self.assertEqual(params["CacheControl"], CACHE_CONTROL)
        self.assertEqual(params["MetadataDirective"], "REPLACE")
        self.assertEqual(params["ContentType"], "application/pdf")
        self.assertEqual(params["ContentDisposition"], "attachment")
        self.assertEqual(params["Metadata"], {"foo": "bar"})
        self.assertNotIn("ACL", params)
        self.anonymous_mock.head_object.assert_not_called()

    def test_public_read_sets_acls(self):
        self._create_image()
        self._create_document()
        self.objects = {
            "original_images/photo.jpg": {"ContentType": "image/jpeg"},
            "documents/report.pdf": {"ContentType": "application/pdf"},
        }
        self._call(self._storage(), "--public-read")
        copied = self._copied_keys()
        self.assertEqual(copied["original_images/photo.jpg"]["ACL"], "public-read")
        self.assertEqual(copied["documents/report.pdf"]["ACL"], "private")

    def test_public_read_does_not_skip_private_images(self):
        self._create_image("private.jpg")
        self._create_image("public.jpg")
        self.objects = {
            "original_images/private.jpg": {"CacheControl": CACHE_CONTROL},
            "original_images/public.jpg": {"CacheControl": CACHE_CONTROL},
        }
        self.public_keys = {"original_images/public.jpg"}
        self._call(self._storage(), "--public-read")
        self.assertEqual(set(self._copied_keys()), {"original_images/private.jpg"})

    def test_public_storage_implies_public_read(self):
        self._create_image()
        self.objects = {"original_images/photo.jpg": {}}
        self.public_keys = {"original_images/photo.jpg"}
        self._call(self._storage(cls=PublicImagesS3Storage))
        self.assertEqual(self._copied_keys()["original_images/photo.jpg"]["ACL"], "public-read")

    def test_missing_objects_are_reported_without_failing(self):
        self._create_image()
        output = self._call(self._storage())
        self.assertIn("Missing from the bucket: original_images/photo.jpg", output)
        self.assertIn("1 missing", output)
        self.client_mock.copy_object.assert_not_called()

    def test_access_denied_on_copy_stops_with_permission_name(self):
        self._create_image("a.jpg")
        self._create_image("b.jpg")
        self.objects = {"original_images/a.jpg": {}, "original_images/b.jpg": {}}
        self.client_mock.copy_object.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "CopyObject")
        with self.assertRaisesMessage(CommandError, "s3:PutObjectAcl"):
            self._call(self._storage(), "--public-read")
        self.assertEqual(self.client_mock.copy_object.call_count, 1)

    def test_unreadable_objects_are_skipped(self):
        # Without s3:ListBucket, a missing object answers 403 instead of 404.
        self._create_image("gone.jpg")
        self._create_image("here.jpg")
        self.objects = {"original_images/here.jpg": {}}
        self.missing_code = "403"
        output = self._call(self._storage())
        self.assertIn("Unreadable (missing or access denied): original_images/gone.jpg", output)
        self.assertIn("1 unreadable", output)
        self.assertEqual(set(self._copied_keys()), {"original_images/here.jpg"})

    def test_access_denied_on_every_head_fails_with_permission_name(self):
        self._create_image()
        self.client_mock.head_object.side_effect = ClientError({"Error": {"Code": "403"}}, "HeadObject")
        with self.assertRaisesMessage(CommandError, "s3:GetObject"):
            self._call(self._storage())

    def test_other_errors_make_the_command_fail(self):
        self._create_image()
        self.objects = {"original_images/photo.jpg": {}}
        self.client_mock.copy_object.side_effect = ClientError({"Error": {"Code": "InternalError"}}, "CopyObject")
        with self.assertRaisesMessage(CommandError, "1 object(s) could not be processed"):
            self._call(self._storage())


@override_settings(WAGTAILDOCS_SERVE_METHOD="serve_view")
class RestrictedDocumentServeTestCase(TestCase):
    def setUp(self):
        root = Collection.get_first_root_node()
        collection = root.add_child(name="Private")
        CollectionViewRestriction.objects.create(collection=collection, restriction_type="login")
        self.document = get_document_model().objects.create(
            title="Private report",
            file=ContentFile(b"secret", name="private-report.txt"),
            collection=collection,
        )

    def tearDown(self):
        self.document.file.delete(save=False)

    def test_anonymous_is_refused(self):
        response = self.client.get(self.document.url)
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response["Location"], self.document.file.url)
        self.assertIn("login", response["Location"])

    def test_logged_in_user_is_served_without_redirect(self):
        user = get_user_model().objects.create_user("reader", "reader@example.org", "pass")
        self.client.force_login(user)
        response = self.client.get(self.document.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"secret")
