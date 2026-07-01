"""
Set or update Cache-Control headers on all existing objects in the S3 bucket.

This is a one-shot backfill command for objects uploaded before the
``object_parameters["CacheControl"]`` setting was added to ``config/settings.py``.

Usage::

    python manage.py set_s3_cache_control                              # apply
    python manage.py set_s3_cache_control --dry-run                     # preview
    python manage.py set_s3_cache_control --cache-control "public, max-age=604800"  # custom value

The default ``cache-control`` value matches ``config/settings.py``:
``public, max-age=31536000, immutable``.
"""

import os

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Set Cache-Control headers on all existing S3 media objects."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview objects that would be updated without making changes.",
        )
        parser.add_argument(
            "--cache-control",
            default="",
            help='Cache-Control header value (default: same as settings.py, i.e. "public, max-age=31536000, immutable").',
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        header_value = options["cache-control"] or os.getenv(
            "S3_CACHE_CONTROL", settings.MEDIA_CACHE_CONTROL
        )

        s3_config = self._get_s3_config()
        if not s3_config:
            raise CommandError(
                "S3 is not configured. Set S3_HOST, S3_KEY_ID, S3_KEY_SECRET, "
                "and S3_BUCKET_NAME environment variables."
            )

        self.stdout.write(f"S3 endpoint: {s3_config['endpoint_url']}")
        self.stdout.write(f"S3 bucket: {s3_config['bucket_name']}")
        self.stdout.write(f"S3 location prefix: {s3_config['location'] or '(none)'}")
        self.stdout.write(f"Cache-Control value: {header_value}")
        self.stdout.write("")

        self._set_cache_control(s3_config, header_value, dry_run)

    # ─────────────────────────────────────
    # S3 configuration helpers
    # ─────────────────────────────────────

    def _get_s3_config(self):
        """Read S3 configuration from environment (same vars as settings.py)."""
        host = os.getenv("S3_HOST")
        if not host:
            return None

        protocol = os.getenv("S3_PROTOCOL", "https")
        return {
            "endpoint_url": f"{protocol}://{host}",
            "bucket_name": os.getenv("S3_BUCKET_NAME", ""),
            "access_key": os.getenv("S3_KEY_ID", ""),
            "secret_key": os.getenv("S3_KEY_SECRET", ""),
            "region_name": os.getenv("S3_BUCKET_REGION", "fr"),
            "location": os.getenv("S3_LOCATION", ""),
        }

    def _get_s3_client(self, s3_config):
        """Create a boto3 S3 client."""
        return boto3.client(
            "s3",
            endpoint_url=s3_config["endpoint_url"],
            aws_access_key_id=s3_config["access_key"],
            aws_secret_access_key=s3_config["secret_key"],
            region_name=s3_config["region_name"],
        )

    # ─────────────────────────────────────
    # Update Cache-Control on existing objects
    # ─────────────────────────────────────

    def _set_cache_control(self, s3_config, header_value, dry_run):
        self.stdout.write(self.style.MIGRATE_HEADING("Listing objects in S3 bucket…"))

        client = self._get_s3_client(s3_config)
        bucket = s3_config["bucket_name"]
        location = s3_config["location"]

        # Build prefix if location is set
        prefix = f"{location.rstrip('/')}/" if location else ""

        updated = 0
        skipped = 0
        errors = 0

        paginator = client.get_paginator("list_objects_v2")

        try:
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                contents = page.get("Contents", [])
                for obj in contents:
                    key = obj["Key"]

                    # Check current Cache-Control
                    try:
                        head = client.head_object(Bucket=bucket, Key=key)
                    except ClientError as e:
                        errors += 1
                        self.stderr.write(self.style.ERROR(f"  Error reading {key}: {e}"))
                        continue

                    current_cc = head.get("CacheControl", "")
                    if current_cc == header_value:
                        skipped += 1
                        continue

                    if dry_run:
                        self.stdout.write(
                            f"  [DRY RUN] Would update: {key}  "
                            f"(current: {current_cc or 'none'})"
                        )
                        updated += 1
                        continue

                    # Copy the object onto itself with new Cache-Control
                    try:
                        client.copy_object(
                            Bucket=bucket,
                            Key=key,
                            CopySource={"Bucket": bucket, "Key": key},
                            MetadataDirective="REPLACE",
                            CacheControl=header_value,
                            # Preserve the original content type
                            ContentType=head.get("ContentType", "application/octet-stream"),
                        )
                        updated += 1
                        self.stdout.write(f"  Updated: {key}")
                    except ClientError as e:
                        errors += 1
                        self.stderr.write(self.style.ERROR(f"  Error updating {key}: {e}"))

        except ClientError as e:
            raise CommandError(f"Failed to list objects: {e}")

        self.stdout.write("")
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [DRY RUN] Would update {updated} object(s), "
                    f"{skipped} already have the target Cache-Control."
                )
            )
        else:
            parts = [f"Updated {updated} object(s), {skipped} already had the correct header."]
            if errors:
                parts.append(f"{errors} error(s).")
            self.stdout.write(self.style.SUCCESS(" ".join(parts)))
