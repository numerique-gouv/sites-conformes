from django.db import migrations

from sites_conformes.core.migration_utils import rename_revision_field


class Migration(migrations.Migration):
    dependencies = [
        ("sites_conformes_blog", "0069_category_to_core_state"),
    ]

    operations = [
        migrations.RenameField(model_name="blogentrypage", old_name="blog_categories", new_name="categories"),
        migrations.RunPython(*rename_revision_field("sites_conformes_blog", "BlogEntryPage", "blog_categories", "categories")),
    ]
