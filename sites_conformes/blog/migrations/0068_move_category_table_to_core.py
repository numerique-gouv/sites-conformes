from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sites_conformes_blog", "0067_alter_blogentrypage_body_alter_blogindexpage_body_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterModelTable(name="category", table="sites_conformes_core_category"),
            ],
        ),
    ]
