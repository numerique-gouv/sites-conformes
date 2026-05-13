import mimetypes
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from db_storage.models import StoredFile


class Command(BaseCommand):
    help = "Migrate existing media files from the filesystem to the database storage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List files that would be migrated without actually migrating them.",
        )

    def handle(self, *args, **options):
        media_root = getattr(settings, "MEDIA_ROOT", "")
        if not media_root or not os.path.isdir(media_root):
            self.stderr.write(self.style.ERROR(f"MEDIA_ROOT '{media_root}' is not a valid directory."))
            return

        dry_run = options["dry_run"]
        count = 0
        skipped = 0

        for root, dirs, files in os.walk(media_root):
            for filename in files:
                full_path = os.path.join(root, filename)
                relative_path = os.path.relpath(full_path, media_root)

                if StoredFile.objects.filter(name=relative_path).exists():
                    skipped += 1
                    continue

                if dry_run:
                    self.stdout.write(f"  [DRY RUN] Would migrate: {relative_path}")
                    count += 1
                    continue

                with open(full_path, "rb") as f:
                    data = f.read()

                content_type, _ = mimetypes.guess_type(filename)
                content_type = content_type or "application/octet-stream"

                StoredFile.objects.create(
                    name=relative_path,
                    content=data,
                    content_type=content_type,
                    size=len(data),
                )
                count += 1
                self.stdout.write(f"  Migrated: {relative_path}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"\n{count} file(s) would be migrated, {skipped} already exist."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n{count} file(s) migrated, {skipped} skipped (already exist)."))
