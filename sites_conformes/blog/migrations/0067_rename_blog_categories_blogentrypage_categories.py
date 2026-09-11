from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sites_conformes_blog", "0066_category_to_core_state"),
    ]

    operations = [
        migrations.RenameField(model_name="blogentrypage", old_name="blog_categories", new_name="categories"),
    ]
