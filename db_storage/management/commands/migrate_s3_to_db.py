import mimetypes

import boto3
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from wagtail.fields import RichTextField
from wagtail.models import Revision

from db_storage.models import StoredFile


class Command(BaseCommand):
    help = (
        "Migrate all media files from S3 to the database storage, "
        "then update any hardcoded S3 URLs found in page content."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be done without making changes.",
        )
        parser.add_argument(
            "--skip-files",
            action="store_true",
            help="Skip file transfer, only update URLs in content.",
        )
        parser.add_argument(
            "--skip-urls",
            action="store_true",
            help="Skip URL replacement, only transfer files.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        skip_files = options["skip_files"]
        skip_urls = options["skip_urls"]

        s3_config = self._get_s3_config()
        if not s3_config:
            raise CommandError(
                "S3 is not configured. Set S3_HOST, S3_KEY_ID, S3_KEY_SECRET, "
                "and S3_BUCKET_NAME environment variables."
            )

        s3_base_url = self._get_s3_base_url(s3_config)
        self.stdout.write(f"S3 endpoint: {s3_config['endpoint_url']}")
        self.stdout.write(f"S3 bucket: {s3_config['bucket_name']}")
        self.stdout.write(f"S3 location prefix: {s3_config['location'] or '(none)'}")
        self.stdout.write(f"S3 base URL for content: {s3_base_url}")
        self.stdout.write("")

        if not skip_files:
            self._transfer_files(s3_config, dry_run)

        if not skip_urls:
            self._update_urls(s3_base_url, dry_run)

    # ─────────────────────────────────────
    # S3 configuration helpers
    # ─────────────────────────────────────

    def _get_s3_config(self):
        """Read S3 configuration from environment (same vars as settings.py)."""
        import os

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

    def _get_s3_base_url(self, s3_config):
        """Build the base URL that S3 files are served from."""
        base = s3_config["endpoint_url"]
        bucket = s3_config["bucket_name"]
        location = s3_config["location"]

        # S3 URLs are typically: endpoint/bucket/location/path or endpoint/path
        # depending on configuration. Build the most likely prefix.
        url = f"{base}/{bucket}"
        if location:
            url = f"{url}/{location}"
        return url

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
    # Step 1: Transfer files from S3 → StoredFile
    # ─────────────────────────────────────

    def _transfer_files(self, s3_config, dry_run):
        self.stdout.write(self.style.MIGRATE_HEADING("Step 1: Transferring files from S3 to database..."))

        client = self._get_s3_client(s3_config)
        bucket = s3_config["bucket_name"]
        prefix = s3_config["location"]
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        transferred = 0
        skipped = 0
        errors = 0

        paginator = client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix)

        for page in page_iterator:
            for obj in page.get("Contents", []):
                s3_key = obj["Key"]

                # Strip the location prefix to get the relative path
                if prefix and s3_key.startswith(prefix):
                    relative_path = s3_key[len(prefix) :]
                else:
                    relative_path = s3_key

                # Skip "directories" (keys ending with /)
                if not relative_path or relative_path.endswith("/"):
                    continue

                if StoredFile.objects.filter(name=relative_path).exists():
                    skipped += 1
                    continue

                if dry_run:
                    size_kb = obj.get("Size", 0) / 1024
                    self.stdout.write(f"  [DRY RUN] Would transfer: {relative_path} ({size_kb:.1f} KB)")
                    transferred += 1
                    continue

                try:
                    response = client.get_object(Bucket=bucket, Key=s3_key)
                    data = response["Body"].read()

                    content_type = response.get("ContentType", "")
                    if not content_type:
                        content_type, _ = mimetypes.guess_type(relative_path)
                        content_type = content_type or "application/octet-stream"

                    StoredFile.objects.create(
                        name=relative_path,
                        content=data,
                        content_type=content_type,
                        size=len(data),
                    )
                    transferred += 1
                    self.stdout.write(f"  Transferred: {relative_path} ({len(data) / 1024:.1f} KB)")

                except Exception as e:
                    errors += 1
                    self.stderr.write(self.style.ERROR(f"  Error on {s3_key}: {e}"))

        self.stdout.write("")
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"  [DRY RUN] Would transfer {transferred} file(s), {skipped} already in DB.")
            )
        else:
            msg = f"  Transferred {transferred} file(s), {skipped} skipped (already in DB)."
            if errors:
                msg += f" {errors} error(s)."
            self.stdout.write(self.style.SUCCESS(msg))
        self.stdout.write("")

    # ─────────────────────────────────────
    # Step 2: Update hardcoded S3 URLs in content
    # ─────────────────────────────────────

    def _update_urls(self, s3_base_url, dry_run):
        self.stdout.write(self.style.MIGRATE_HEADING("Step 2: Updating hardcoded S3 URLs in content..."))

        total_updates = 0

        # 2a. Update Wagtail page revisions (StreamField / RichTextField JSON)
        total_updates += self._update_revisions(s3_base_url, dry_run)

        # 2b. Update URL fields on models (URLField / CharField that might contain S3 URLs)
        total_updates += self._update_url_fields(s3_base_url, dry_run)

        self.stdout.write("")
        if total_updates:
            self.stdout.write(self.style.SUCCESS(f"  Total URL replacements: {total_updates}"))
        else:
            self.stdout.write(self.style.SUCCESS("  No hardcoded S3 URLs found in content."))
        self.stdout.write("")

    def _update_revisions(self, s3_base_url, dry_run):
        """Scan and update S3 URLs in Wagtail page revision content."""
        updates = 0
        revisions = Revision.objects.filter(content_json__contains=s3_base_url)
        count = revisions.count()

        if count:
            self.stdout.write(f"  Found {count} revision(s) containing S3 URLs.")

        for revision in revisions.iterator():
            old_content = revision.content_json
            new_content = old_content.replace(s3_base_url, "/db-storage/serve?name=")

            if old_content != new_content:
                if dry_run:
                    self.stdout.write(f"  [DRY RUN] Would update revision {revision.pk}")
                else:
                    revision.content_json = new_content
                    revision.save(update_fields=["content_json"])
                    self.stdout.write(f"  Updated revision {revision.pk}")
                updates += 1

        return updates

    def _update_url_fields(self, s3_base_url, dry_run):
        """Scan URLField / CharField on all models for hardcoded S3 URLs."""
        updates = 0

        # Collect all concrete models with URLField or CharField
        for model in self._get_models_with_url_fields():
            model_name = f"{model._meta.app_label}.{model._meta.model_name}"

            for field in model._meta.get_fields():
                if not isinstance(field, (models.URLField, models.CharField)):
                    continue
                if isinstance(field, (models.AutoField, models.BigAutoField)):
                    continue
                if not hasattr(field, "column"):
                    continue

                field_name = field.name
                lookup = {f"{field_name}__contains": s3_base_url}

                try:
                    qs = model.objects.filter(**lookup)
                except Exception:
                    continue

                for obj in qs.iterator():
                    old_value = getattr(obj, field_name, "")
                    if not old_value or s3_base_url not in old_value:
                        continue

                    new_value = old_value.replace(s3_base_url, "/db-storage/serve?name=")

                    if dry_run:
                        self.stdout.write(f"  [DRY RUN] Would update {model_name}.{field_name} " f"(pk={obj.pk})")
                    else:
                        setattr(obj, field_name, new_value)
                        obj.save(update_fields=[field_name])
                        self.stdout.write(f"  Updated {model_name}.{field_name} (pk={obj.pk})")
                    updates += 1

        # Also scan RichTextField content on live pages
        updates += self._update_rich_text_fields(s3_base_url, dry_run)

        return updates

    def _update_rich_text_fields(self, s3_base_url, dry_run):
        """Scan RichTextField values on all models for hardcoded S3 URLs."""
        updates = 0

        for model in self._get_models_with_rich_text():
            model_name = f"{model._meta.app_label}.{model._meta.model_name}"

            for field in model._meta.get_fields():
                if not isinstance(field, RichTextField):
                    continue

                field_name = field.name
                lookup = {f"{field_name}__contains": s3_base_url}

                try:
                    qs = model.objects.filter(**lookup)
                except Exception:
                    continue

                for obj in qs.iterator():
                    old_value = getattr(obj, field_name, "")
                    if not old_value or s3_base_url not in old_value:
                        continue

                    new_value = old_value.replace(s3_base_url, "/db-storage/serve?name=")

                    if dry_run:
                        self.stdout.write(f"  [DRY RUN] Would update {model_name}.{field_name} " f"(pk={obj.pk})")
                    else:
                        setattr(obj, field_name, new_value)
                        obj.save(update_fields=[field_name])
                        self.stdout.write(f"  Updated {model_name}.{field_name} (pk={obj.pk})")
                    updates += 1

        return updates

    def _get_models_with_url_fields(self):
        """Return all concrete Django models that have URLField or CharField."""
        from django.apps import apps

        result = []
        for model in apps.get_models():
            if model._meta.abstract or model._meta.proxy:
                continue
            for field in model._meta.get_fields():
                if isinstance(field, (models.URLField,)):
                    result.append(model)
                    break
        return result

    def _get_models_with_rich_text(self):
        """Return all concrete Django models that have RichTextField."""
        from django.apps import apps

        result = []
        for model in apps.get_models():
            if model._meta.abstract or model._meta.proxy:
                continue
            for field in model._meta.get_fields():
                if isinstance(field, RichTextField):
                    result.append(model)
                    break
        return result
