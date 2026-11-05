from django.db import migrations

from sites_conformes.core.migration_utils import rename_revision_field


class Migration(migrations.Migration):
    dependencies = [
        ("sites_conformes_core", "0087_category"),
    ]

    operations = [
        migrations.RenameField(model_name="catalogindexpage", old_name="entries_per_page", new_name="posts_per_page"),
        migrations.RunPython(*rename_revision_field("sites_conformes_core", "CatalogIndexPage", "entries_per_page", "posts_per_page")),
    ]
