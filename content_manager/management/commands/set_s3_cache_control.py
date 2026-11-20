"""
Set or update Cache-Control headers (and optionally public-read ACLs on images)
on the S3 objects of all files known to Wagtail (images, renditions, documents).

This is a backfill command for objects uploaded before
``object_parameters["CacheControl"]`` and ``PublicImagesS3Storage`` were added
to ``config/settings.py``. It is idempotent and can be run several times.

It only needs the permissions the app already has (``s3:GetObject``,
``s3:PutObject``, ``s3:PutObjectAcl``): object keys are read from the database
instead of listing the bucket (no ``s3:ListBucket``), and whether an object is
public is checked with an anonymous HEAD request (no ``s3:GetObjectAcl``).

Usage::

    python manage.py set_s3_cache_control --dry-run                     # preview
    python manage.py set_s3_cache_control                               # apply
    python manage.py set_s3_cache_control --public-read                 # also make images public
    python manage.py set_s3_cache_control --cache-control "public, max-age=604800"

The default Cache-Control value matches ``config/settings.py``:
``S3_CACHE_CONTROL``, falling back to ``MEDIA_CACHE_CONTROL``.

Adapted from the sites-conformes upstream command (PR #537).
"""

import os

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from storages.backends.s3 import S3Storage
from storages.utils import clean_name
from wagtail.documents import get_document_model
from wagtail.images import get_image_model

from content_manager.storages import PUBLIC_ACL, PublicImagesS3Storage, is_public_key

# Metadata that copy_object(MetadataDirective="REPLACE") would drop if not passed again.
PRESERVED_HEADERS = ("ContentType", "ContentDisposition", "ContentEncoding", "ContentLanguage")

ACCESS_DENIED_CODES = ("403", "AccessDenied")
NOT_FOUND_CODES = ("404", "NoSuchKey", "NotFound")


def error_code(error: ClientError) -> str:
    return str(error.response.get("Error", {}).get("Code", ""))


class Command(BaseCommand):
    help = (
        "Set Cache-Control headers (and optionally public-read ACLs on images) "
        "on the S3 objects of Wagtail images, renditions and documents."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview objects that would be updated without making changes.",
        )
        parser.add_argument(
            "--cache-control",
            default="",
            help="Cache-Control header value (default: S3_CACHE_CONTROL, then MEDIA_CACHE_CONTROL).",
        )
        parser.add_argument(
            "--public-read",
            action="store_true",
            help="Also set a public-read ACL on images (documents stay private). "
            "Implied when S3_PUBLIC_HOST is set.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        header_value = options["cache_control"] or os.getenv("S3_CACHE_CONTROL", settings.MEDIA_CACHE_CONTROL)

        storage = default_storage
        if not isinstance(storage, S3Storage):
            raise CommandError("The default storage is not S3. Set the S3_* environment variables.")

        # A self-copy resets ACLs, so once images are public (S3_PUBLIC_HOST set),
        # ACLs must always be managed, even without --public-read.
        public_read = options["public_read"] or isinstance(storage, PublicImagesS3Storage)

        client = storage.connection.meta.client
        anonymous_client = storage.unsigned_connection.meta.client
        bucket = storage.bucket_name
        location = storage.location.strip("/")

        self.stdout.write(f"S3 endpoint: {storage.endpoint_url}")
        self.stdout.write(f"S3 bucket: {bucket}")
        self.stdout.write(f"S3 location prefix: {location or '(none)'}")
        self.stdout.write(f"Cache-Control value: {header_value}")
        self.stdout.write(f"Public-read on images: {'yes' if public_read else 'no'}")
        self.stdout.write("")

        updated = 0
        skipped = 0
        missing = 0
        unreadable = 0
        errors = 0

        for key in self._iter_keys(storage):
            make_public = public_read and is_public_key(key, location)

            try:
                head = client.head_object(Bucket=bucket, Key=key)
            except ClientError as e:
                code = error_code(e)
                if code in NOT_FOUND_CODES:
                    missing += 1
                    self.stdout.write(self.style.WARNING(f"  Missing from the bucket: {key}"))
                    continue
                if code in ACCESS_DENIED_CODES:
                    # Without s3:ListBucket, S3 answers 403 instead of 404 for missing
                    # objects, so a missing file and a real denial look the same.
                    unreadable += 1
                    self.stdout.write(self.style.WARNING(f"  Unreadable (missing or access denied): {key}"))
                    continue
                errors += 1
                self.stderr.write(self.style.ERROR(f"  Error reading {key}: {e}"))
                continue

            is_public = self._is_public(anonymous_client, bucket, key) if make_public else None
            current_cc = head.get("CacheControl", "")
            if current_cc == header_value and (not make_public or is_public):
                skipped += 1
                continue

            if dry_run:
                details = f"current Cache-Control: {current_cc or 'none'}"
                if make_public:
                    details += f", public: {'yes' if is_public else 'no'}"
                self.stdout.write(f"  [DRY RUN] Would update: {key}  ({details})")
                updated += 1
                continue

            try:
                self._update_object(client, bucket, key, head, header_value, make_public, public_read)
            except ClientError as e:
                if error_code(e) in ACCESS_DENIED_CODES:
                    raise CommandError(
                        f"Access denied updating {key}: the S3 user needs s3:PutObject"
                        + (" and s3:PutObjectAcl." if public_read else ".")
                    )
                errors += 1
                self.stderr.write(self.style.ERROR(f"  Error updating {key}: {e}"))
                continue

            updated += 1
            self.stdout.write(f"  Updated: {key}")

        self.stdout.write("")
        verb = "[DRY RUN] Would update" if dry_run else "Updated"
        summary = (
            f"{verb} {updated} object(s), {skipped} already up to date, {missing} missing, "
            f"{unreadable} unreadable (missing or access denied)."
        )
        if errors:
            summary += f" {errors} error(s)."
        self.stdout.write(self.style.SUCCESS(summary) if not errors else self.style.WARNING(summary))

        if unreadable and not (updated or skipped):
            raise CommandError(
                "No object could be read. Check that the S3 user has s3:GetObject on this bucket, "
                "and that the files listed in the database exist in it."
            )
        if errors:
            raise CommandError(f"{errors} object(s) could not be processed.")

    def _iter_keys(self, storage):
        """Yield the S3 keys of all Wagtail images, renditions and documents, without duplicates."""
        image_model = get_image_model()
        models = (image_model, image_model.get_rendition_model(), get_document_model())
        seen = set()
        for model in models:
            for name in model.objects.values_list("file", flat=True).iterator():
                if not name:
                    continue
                key = storage._normalize_name(clean_name(name))
                if key in seen:
                    continue
                seen.add(key)
                yield key

    def _is_public(self, anonymous_client, bucket, key) -> bool:
        """An anonymous HEAD request only succeeds on publicly readable objects."""
        try:
            anonymous_client.head_object(Bucket=bucket, Key=key)
        except ClientError as e:
            if error_code(e) in ACCESS_DENIED_CODES + NOT_FOUND_CODES:
                return False
            # e.g. OVHcloud answers 400 to anonymous path-style requests.
            raise CommandError(
                f"Anonymous request on {key} rejected ({error_code(e)}): check S3_ADDRESSING_STYLE "
                "(OVHcloud requires 'virtual')."
            )
        return True

    def _update_object(self, client, bucket, key, head, header_value, make_public, public_read):
        """Copy the object onto itself with the new Cache-Control, keeping its metadata."""
        params = {
            "Bucket": bucket,
            "Key": key,
            "CopySource": {"Bucket": bucket, "Key": key},
            "MetadataDirective": "REPLACE",
            "CacheControl": header_value,
            "Metadata": head.get("Metadata", {}),
        }
        for header in PRESERVED_HEADERS:
            if head.get(header):
                params[header] = head[header]
        params.setdefault("ContentType", "application/octet-stream")

        # A self-copy resets the ACL to private: set it explicitly when managing ACLs.
        if make_public:
            params["ACL"] = PUBLIC_ACL
        elif public_read:
            params["ACL"] = "private"

        client.copy_object(**params)
