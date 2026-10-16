from django.db import migrations

from sites_conformes.core.migration_utils import rename_revision_field


class Migration(migrations.Migration):
    dependencies = [
        ("sites_conformes_events", "0040_category_to_core_state"),
    ]

    operations = [
        migrations.RenameField(model_name="evententrypage", old_name="event_categories", new_name="categories"),
        migrations.RunPython(*rename_revision_field("sites_conformes_events", "EventEntryPage", "event_categories", "categories")),
    ]
