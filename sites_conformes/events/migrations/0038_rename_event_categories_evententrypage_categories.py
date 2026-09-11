from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sites_conformes_events", "0037_category_to_core_state"),
    ]

    operations = [
        migrations.RenameField(model_name="evententrypage", old_name="event_categories", new_name="categories"),
    ]
