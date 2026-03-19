import boto3
from django.core.management.base import BaseCommand, CommandError

from db_storage.models import StoredFile


class Command(BaseCommand):
    help = "Migrate all media files from the database storage to S3."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be done without making changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        s3_config = self._get_s3_config()
        if not s3_config:
            raise CommandError(
                "S3 is not configured. Set S3_HOST, S3_KEY_ID, S3_KEY_SECRET, "
                "and S3_BUCKET_NAME environment variables."
            )

        self.stdout.write(f"S3 endpoint: {s3_config['endpoint_url']}")
        self.stdout.write(f"S3 bucket: {s3_config['bucket_name']}")
        self.stdout.write(f"S3 location prefix: {s3_config['location'] or '(none)'}")
        self.stdout.write("")

        self._transfer_files(s3_config, dry_run)

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
    # Transfer files from StoredFile → S3
    # ─────────────────────────────────────

    def _transfer_files(self, s3_config, dry_run):
        self.stdout.write(
            self.style.MIGRATE_HEADING("Transferring files from database to S3...")
        )

        client = self._get_s3_client(s3_config)
        bucket = s3_config["bucket_name"]
        location = s3_config["location"]

        transferred = 0
        skipped = 0
        errors = 0

        total = StoredFile.objects.count()
        if total == 0:
            self.stdout.write("  No files in database storage.")
            return

        self.stdout.write(f"  {total} file(s) in database storage.")
        self.stdout.write("")

        for stored_file in StoredFile.objects.all().iterator():
            s3_key = stored_file.name
            if location:
                s3_key = f"{location}/{stored_file.name}"

            # Check if already exists on S3
            if not dry_run:
                try:
                    client.head_object(Bucket=bucket, Key=s3_key)
                    skipped += 1
                    continue
                except client.exceptions.ClientError:
                    pass  # File does not exist on S3, proceed

            if dry_run:
                size_kb = stored_file.size / 1024 if stored_file.size else 0
                self.stdout.write(
                    f"  [DRY RUN] Would upload: {stored_file.name} ({size_kb:.1f} KB)"
                )
                transferred += 1
                continue

            try:
                client.put_object(
                    Bucket=bucket,
                    Key=s3_key,
                    Body=bytes(stored_file.content),
                    ContentType=stored_file.content_type or "application/octet-stream",
                )
                transferred += 1
                size_kb = stored_file.size / 1024 if stored_file.size else 0
                self.stdout.write(f"  Uploaded: {stored_file.name} ({size_kb:.1f} KB)")

            except Exception as e:
                errors += 1
                self.stderr.write(
                    self.style.ERROR(f"  Error on {stored_file.name}: {e}")
                )

        self.stdout.write("")
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [DRY RUN] Would upload {transferred} file(s), "
                    f"{skipped} already on S3."
                )
            )
        else:
            msg = (
                f"  Uploaded {transferred} file(s), "
                f"{skipped} skipped (already on S3)."
            )
            if errors:
                msg += f" {errors} error(s)."
            self.stdout.write(self.style.SUCCESS(msg))
