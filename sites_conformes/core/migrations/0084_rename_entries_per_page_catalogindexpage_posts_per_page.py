from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sites_conformes_core", "0083_category"),
    ]

    operations = [
        migrations.RenameField(model_name="catalogindexpage", old_name="entries_per_page", new_name="posts_per_page"),
    ]
