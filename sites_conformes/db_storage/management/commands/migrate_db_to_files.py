import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from wagtail.fields import RichTextField
from wagtail.models import Revision

from db_storage.models import StoredFile


class Command(BaseCommand):
    help = (
        "Migrate all media files from the database storage to the filesystem, "
        "then update any hardcoded DB storage URLs found in page content."
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

        media_root = getattr(settings, "MEDIA_ROOT", "")
        if not media_root:
            raise CommandError("MEDIA_ROOT is not configured.")

        media_url = getattr(settings, "MEDIA_URL", "/media/")

        self.stdout.write(f"MEDIA_ROOT: {media_root}")
        self.stdout.write(f"MEDIA_URL: {media_url}")
        self.stdout.write("")

        if not skip_files:
            self._transfer_files(media_root, dry_run)

        if not skip_urls:
            self._update_urls(media_url, dry_run)

    # ─────────────────────────────────────
    # Step 1: Transfer files from StoredFile → filesystem
    # ─────────────────────────────────────

    def _transfer_files(self, media_root, dry_run):
        self.stdout.write(self.style.MIGRATE_HEADING("Step 1: Transferring files from database to filesystem…"))

        total = StoredFile.objects.count()
        if total == 0:
            self.stdout.write("  No files in database storage.")
            return

        self.stdout.write(f"  {total} file(s) in database storage.")
        self.stdout.write("")

        transferred = 0
        skipped = 0
        errors = 0

        if not dry_run:
            os.makedirs(media_root, exist_ok=True)

        for stored_file in StoredFile.objects.all().iterator():
            dest_path = os.path.join(media_root, stored_file.name)

            if os.path.exists(dest_path):
                skipped += 1
                continue

            size_kb = stored_file.size / 1024 if stored_file.size else 0

            if dry_run:
                self.stdout.write(f"  [DRY RUN] Would write: {stored_file.name} ({size_kb:.1f} KB)")
                transferred += 1
                continue

            try:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, "wb") as f:
                    f.write(bytes(stored_file.content))
                transferred += 1
                self.stdout.write(f"  Written: {stored_file.name} ({size_kb:.1f} KB)")
            except Exception as e:
                errors += 1
                self.stderr.write(self.style.ERROR(f"  Error on {stored_file.name}: {e}"))

        self.stdout.write("")
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"  [DRY RUN] Would write {transferred} file(s), {skipped} already on filesystem.")
            )
        else:
            msg = f"  Written {transferred} file(s), {skipped} skipped (already on filesystem)."
            if errors:
                msg += f" {errors} error(s)."
            self.stdout.write(self.style.SUCCESS(msg))
        self.stdout.write("")

    # ─────────────────────────────────────
    # Step 2: Update hardcoded DB storage URLs in content
    # ─────────────────────────────────────

    def _update_urls(self, media_url, dry_run):
        self.stdout.write(self.style.MIGRATE_HEADING("Step 2: Updating hardcoded DB storage URLs in content…"))

        db_storage_prefix = "/db-storage/serve?name="
        total_updates = 0

        total_updates += self._update_revisions(db_storage_prefix, media_url, dry_run)
        total_updates += self._update_url_fields(db_storage_prefix, media_url, dry_run)

        self.stdout.write("")
        if total_updates:
            self.stdout.write(self.style.SUCCESS(f"  Total URL replacements: {total_updates}"))
        else:
            self.stdout.write(self.style.SUCCESS("  No hardcoded DB storage URLs found in content."))
        self.stdout.write("")

    def _update_revisions(self, db_storage_prefix, media_url, dry_run):
        import json

        updates = 0

        revisions = Revision.objects.all()
        count = revisions.count()
        self.stdout.write(f"  Scanning {count} revision(s) for DB storage URLs…")

        for revision in revisions.iterator():
            content = revision.content
            if not content:
                continue

            content_str = json.dumps(content, ensure_ascii=False)
            if db_storage_prefix not in content_str:
                continue

            new_content_str = content_str.replace(db_storage_prefix, media_url)

            if dry_run:
                self.stdout.write(f"  [DRY RUN] Would update revision {revision.pk}")
            else:
                revision.content = json.loads(new_content_str)
                revision.save(update_fields=["content"])
                self.stdout.write(f"  Updated revision {revision.pk}")
            updates += 1

        return updates

    def _update_url_fields(self, db_storage_prefix, media_url, dry_run):
        updates = 0

        for model in self._get_models_with_url_fields():
            model_name = f"{model._meta.app_label}.{model._meta.model_name}"

            for field in model._meta.get_fields():
                if not isinstance(field, (models.URLField, models.CharField)):
                    continue
                if not hasattr(field, "column"):
                    continue

                field_name = field.name
                lookup = {f"{field_name}__contains": db_storage_prefix}

                try:
                    qs = model.objects.filter(**lookup)
                except Exception:
                    continue

                for obj in qs.iterator():
                    old_value = getattr(obj, field_name, "")
                    if not old_value or db_storage_prefix not in old_value:
                        continue

                    new_value = old_value.replace(db_storage_prefix, media_url)

                    if dry_run:
                        self.stdout.write(f"  [DRY RUN] Would update {model_name}.{field_name} (pk={obj.pk})")
                    else:
                        setattr(obj, field_name, new_value)
                        obj.save(update_fields=[field_name])
                        self.stdout.write(f"  Updated {model_name}.{field_name} (pk={obj.pk})")
                    updates += 1

        updates += self._update_rich_text_fields(db_storage_prefix, media_url, dry_run)

        return updates

    def _update_rich_text_fields(self, db_storage_prefix, media_url, dry_run):
        updates = 0

        for model in self._get_models_with_rich_text():
            model_name = f"{model._meta.app_label}.{model._meta.model_name}"

            for field in model._meta.get_fields():
                if not isinstance(field, RichTextField):
                    continue

                field_name = field.name
                lookup = {f"{field_name}__contains": db_storage_prefix}

                try:
                    qs = model.objects.filter(**lookup)
                except Exception:
                    continue

                for obj in qs.iterator():
                    old_value = getattr(obj, field_name, "")
                    if not old_value or db_storage_prefix not in old_value:
                        continue

                    new_value = old_value.replace(db_storage_prefix, media_url)

                    if dry_run:
                        self.stdout.write(f"  [DRY RUN] Would update {model_name}.{field_name} (pk={obj.pk})")
                    else:
                        setattr(obj, field_name, new_value)
                        obj.save(update_fields=[field_name])
                        self.stdout.write(f"  Updated {model_name}.{field_name} (pk={obj.pk})")
                    updates += 1

        return updates

    def _get_models_with_url_fields(self):
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
