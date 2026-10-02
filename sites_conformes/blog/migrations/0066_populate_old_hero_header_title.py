from django.db import migrations
from itertools import chain


def populate_header_title(apps, schema_editor):
    """
    Fill the new ``header_title`` field of each ``old_hero`` block with the page
    title so the current rendering is preserved, while leaving editors free to
    set a different editorial title afterwards.
    """
    BlogEntryPage = apps.get_model("sites_conformes_blog", "BlogEntryPage")
    BlogIndexPage = apps.get_model("sites_conformes_blog", "BlogIndexPage")

    pages = chain(BlogEntryPage.objects.all(), BlogIndexPage.objects.all())

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
        ("sites_conformes_blog", "0065_alter_blogentrypage_hero_alter_blogindexpage_hero"),
    ]

    operations = [
        migrations.RunPython(populate_header_title, reverse_code=migrations.RunPython.noop),
    ]
