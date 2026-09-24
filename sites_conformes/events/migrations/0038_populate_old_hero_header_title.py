from django.db import migrations
from itertools import chain


def populate_header_title(apps, schema_editor):
    """
    Fill the new ``header_title`` field of each ``old_hero`` block with the page
    title so the current rendering is preserved, while leaving editors free to
    set a different editorial title afterwards.
    """
    EventEntryPage = apps.get_model("sites_conformes_events", "EventEntryPage")
    EventsIndexPage = apps.get_model("sites_conformes_events", "EventsIndexPage")

    pages = chain(EventEntryPage.objects.all(), EventsIndexPage.objects.all())

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
        ("sites_conformes_events", "0037_alter_evententrypage_hero_alter_eventsindexpage_hero"),
    ]

    operations = [
        migrations.RunPython(populate_header_title, reverse_code=migrations.RunPython.noop),
    ]
