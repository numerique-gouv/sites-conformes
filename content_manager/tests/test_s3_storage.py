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
from wagtail.models import Collection, CollectionViewRestriction

from content_manager.management.commands.set_s3_cache_control import ALL_USERS_URI
from content_manager.storages import PublicImagesS3Storage, is_public_key

COMMAND_MODULE = "content_manager.management.commands.set_s3_cache_control"
CACHE_CONTROL = "public, max-age=600"

PUBLIC_GRANTS = {"Grants": [{"Grantee": {"Type": "Group", "URI": ALL_USERS_URI}, "Permission": "READ"}]}
PRIVATE_GRANTS = {"Grants": [{"Grantee": {"Type": "CanonicalUser", "ID": "owner"}, "Permission": "FULL_CONTROL"}]}


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


class SetS3CacheControlTestCase(SimpleTestCase):
    def setUp(self):
        self.client_mock = MagicMock()
        self.objects = {}
        self.acls = {}
        self.client_mock.get_paginator.return_value.paginate.side_effect = self._paginate
        self.client_mock.head_object.side_effect = lambda Bucket, Key: self.objects[Key]
        self.client_mock.get_object_acl.side_effect = lambda Bucket, Key: self.acls[Key]

    def _paginate(self, Bucket, Prefix):
        return [{"Contents": [{"Key": key} for key in self.objects if key.startswith(Prefix)]}]

    def _storage(self, cls=S3Storage, location=""):
        storage = MagicMock(spec=cls)
        storage.bucket_name = "bucket"
        storage.location = location
        storage.endpoint_url = "https://s3.example.org"
        storage.connection.meta.client = self.client_mock
        return storage

    def _call(self, storage, *args):
        out, err = StringIO(), StringIO()
        with patch(f"{COMMAND_MODULE}.default_storage", storage):
            call_command("set_s3_cache_control", "--cache-control", CACHE_CONTROL, *args, stdout=out, stderr=err)
        return out.getvalue()

    def _copied_keys(self):
        return {c.kwargs["Key"]: c.kwargs for c in self.client_mock.copy_object.call_args_list}

    def test_requires_s3_storage(self):
        with patch(f"{COMMAND_MODULE}.default_storage", MagicMock()):
            with self.assertRaises(CommandError):
                call_command("set_s3_cache_control", stdout=StringIO())

    def test_dry_run_does_not_copy(self):
        self.objects = {"images/a.jpg": {"ContentType": "image/jpeg"}}
        output = self._call(self._storage(), "--dry-run")
        self.client_mock.copy_object.assert_not_called()
        self.assertIn("[DRY RUN] Would update: images/a.jpg", output)

    def test_updates_cache_control_and_keeps_metadata(self):
        self.objects = {
            "documents/report.pdf": {
                "ContentType": "application/pdf",
                "ContentDisposition": "attachment",
                "Metadata": {"foo": "bar"},
            },
            "images/up-to-date.jpg": {"ContentType": "image/jpeg", "CacheControl": CACHE_CONTROL},
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
        self.client_mock.get_object_acl.assert_not_called()

    def test_location_prefix(self):
        self.objects = {"site/images/a.jpg": {}, "other/images/b.jpg": {}}
        self._call(self._storage(location="site"))
        self.assertEqual(set(self._copied_keys()), {"site/images/a.jpg"})

    def test_public_read_sets_acls(self):
        self.objects = {
            "images/a.jpg": {"ContentType": "image/jpeg"},
            "documents/report.pdf": {"ContentType": "application/pdf"},
        }
        self.acls = {"images/a.jpg": PRIVATE_GRANTS}
        self._call(self._storage(), "--public-read")
        copied = self._copied_keys()
        self.assertEqual(copied["images/a.jpg"]["ACL"], "public-read")
        self.assertEqual(copied["documents/report.pdf"]["ACL"], "private")

    def test_public_read_does_not_skip_private_images(self):
        self.objects = {
            "images/private.jpg": {"CacheControl": CACHE_CONTROL},
            "images/public.jpg": {"CacheControl": CACHE_CONTROL},
        }
        self.acls = {"images/private.jpg": PRIVATE_GRANTS, "images/public.jpg": PUBLIC_GRANTS}
        self._call(self._storage(), "--public-read")
        self.assertEqual(set(self._copied_keys()), {"images/private.jpg"})

    def test_public_storage_implies_public_read(self):
        self.objects = {"images/a.jpg": {}}
        self.acls = {"images/a.jpg": PUBLIC_GRANTS}
        self._call(self._storage(cls=PublicImagesS3Storage))
        self.assertEqual(self._copied_keys()["images/a.jpg"]["ACL"], "public-read")

    def test_errors_make_the_command_fail(self):
        self.objects = {"images/a.jpg": {}}
        self.client_mock.copy_object.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "CopyObject")
        with self.assertRaises(CommandError):
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
