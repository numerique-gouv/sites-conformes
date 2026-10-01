import json

from django.db import migrations
from wagtail.fields import StreamField

# Keys identifying a CenteredImageBlock value saved before its "alt" field was removed
LEGACY_CENTERED_IMAGE_KEYS = {"image", "alt", "width", "image_ratio"}


def migrate_centered_image_alt(data):
    """
    Recursively walk raw StreamField data and move the legacy "alt" field of
    CenteredImageBlock values into the alt text of their ImageBlock.
    Returns True if data was modified.
    """
    updated = False

    if isinstance(data, dict):
        if LEGACY_CENTERED_IMAGE_KEYS <= data.keys():
            alt = data.pop("alt") or ""
            image = data["image"]
            if alt and isinstance(image, int):
                data["image"] = {"image": image, "decorative": False, "alt_text": alt}
            elif alt and isinstance(image, dict) and not image.get("alt_text"):
                image["alt_text"] = alt
                image["decorative"] = False
            updated = True

        for value in data.values():
            updated = migrate_centered_image_alt(value) or updated

    elif isinstance(data, list):
        for item in data:
            updated = migrate_centered_image_alt(item) or updated

    return updated


def migrate_pages(apps, schema_editor):
    for model in apps.get_models():
        if model._meta.proxy:
            continue
        stream_fields = [f.name for f in model._meta.get_fields() if isinstance(f, StreamField)]
        if not stream_fields:
            continue

        for instance in model.objects.all().iterator():
            updated_fields = []
            for field_name in stream_fields:
                raw_data = list(getattr(instance, field_name).raw_data)
                if migrate_centered_image_alt(raw_data):
                    setattr(instance, field_name, raw_data)
                    updated_fields.append(field_name)

            if updated_fields:
                instance.save(update_fields=updated_fields)


def migrate_revisions(apps, schema_editor):
    # Revisions (drafts, scheduled pages...) store StreamFields as JSON strings
    Revision = apps.get_model("wagtailcore", "Revision")

    for revision in Revision.objects.all().iterator():
        content = revision.content
        updated = False

        for key, value in content.items():
            if not (isinstance(value, str) and value.startswith("[")):
                continue
            try:
                stream_data = json.loads(value)
            except ValueError:
                continue
            if migrate_centered_image_alt(stream_data):
                content[key] = json.dumps(stream_data)
                updated = True

        if updated:
            revision.save(update_fields=["content"])


def migrate_all(apps, schema_editor):
    migrate_pages(apps, schema_editor)
    migrate_revisions(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [
        ("sites_conformes_core", "0084_alter_catalogindexpage_body_alter_contentpage_body"),
        ("sites_conformes_blog", "0066_alter_blogentrypage_body_alter_blogindexpage_body_and_more"),
        ("sites_conformes_events", "0038_alter_evententrypage_body_alter_eventsindexpage_body"),
        ("wagtailcore", "__latest__"),
    ]

    operations = [
        migrations.RunPython(migrate_all, reverse_code=migrations.RunPython.noop),
    ]
