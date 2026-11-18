"""
Set or update Cache-Control headers (and optionally public-read ACLs on images)
on all existing objects of the S3 media bucket.

This is a backfill command for objects uploaded before
``object_parameters["CacheControl"]`` and ``PublicImagesS3Storage`` were added
to ``config/settings.py``. It is idempotent and can be run several times.

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

from content_manager.storages import PUBLIC_ACL, PublicImagesS3Storage, is_public_key

ALL_USERS_URI = "http://acs.amazonaws.com/groups/global/AllUsers"

# Metadata that copy_object(MetadataDirective="REPLACE") would drop if not passed again.
PRESERVED_HEADERS = ("ContentType", "ContentDisposition", "ContentEncoding", "ContentLanguage")


class Command(BaseCommand):
    help = "Set Cache-Control headers (and optionally public-read ACLs on images) on existing S3 media objects."

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
        bucket = storage.bucket_name
        location = storage.location.strip("/")
        prefix = f"{location}/" if location else ""

        self.stdout.write(f"S3 endpoint: {storage.endpoint_url}")
        self.stdout.write(f"S3 bucket: {bucket}")
        self.stdout.write(f"S3 location prefix: {prefix or '(none)'}")
        self.stdout.write(f"Cache-Control value: {header_value}")
        self.stdout.write(f"Public-read on images: {'yes' if public_read else 'no'}")
        self.stdout.write("")

        updated = skipped = errors = 0
        paginator = client.get_paginator("list_objects_v2")

        try:
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    make_public = public_read and is_public_key(key, location)

                    try:
                        head = client.head_object(Bucket=bucket, Key=key)
                        is_public = self._is_public(client, bucket, key) if make_public else None
                    except ClientError as e:
                        errors += 1
                        self.stderr.write(self.style.ERROR(f"  Error reading {key}: {e}"))
                        continue

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
                        updated += 1
                        self.stdout.write(f"  Updated: {key}")
                    except ClientError as e:
                        errors += 1
                        self.stderr.write(self.style.ERROR(f"  Error updating {key}: {e}"))
        except ClientError as e:
            raise CommandError(f"Failed to list objects: {e}")

        self.stdout.write("")
        verb = "[DRY RUN] Would update" if dry_run else "Updated"
        summary = f"{verb} {updated} object(s), {skipped} already up to date."
        if errors:
            summary += f" {errors} error(s)."
        self.stdout.write(self.style.SUCCESS(summary) if not errors else self.style.WARNING(summary))

        if errors:
            raise CommandError(f"{errors} object(s) could not be processed.")

    def _is_public(self, client, bucket, key) -> bool:
        acl = client.get_object_acl(Bucket=bucket, Key=key)
        return any(
            grant.get("Grantee", {}).get("URI") == ALL_USERS_URI
            and grant.get("Permission") in ("READ", "FULL_CONTROL")
            for grant in acl.get("Grants", [])
        )

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
