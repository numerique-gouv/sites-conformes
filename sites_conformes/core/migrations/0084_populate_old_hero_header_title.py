from django.db import migrations
from itertools import chain


def populate_header_title(apps, schema_editor):
    """
    Fill the new ``header_title`` field of each ``old_hero`` block with the page
    title so the current rendering is preserved, while leaving editors free to
    set a different editorial title afterwards.
    """
    ContentPage = apps.get_model("sites_conformes_core", "ContentPage")
    CatalogIndexPage = apps.get_model("sites_conformes_core", "CatalogIndexPage")

    pages = chain(ContentPage.objects.all(), CatalogIndexPage.objects.all())

    for page in pages:
        if not hasattr(page, "hero"):
            continue

        stream_data = page.hero.raw_data
        updated = False

        for block in stream_data:
            if block["type"] == "old_hero":
                value = block.get("value", {})

                if not value.get("header_title"):
                    value["header_title"] = page.title
                    updated = True

        if updated:
            page.hero = stream_data
            page.save()


class Migration(migrations.Migration):

    dependencies = [
        ("sites_conformes_core", "0083_alter_catalogindexpage_hero_alter_contentpage_hero"),
    ]

    operations = [
        migrations.RunPython(populate_header_title, reverse_code=migrations.RunPython.noop),
    ]
