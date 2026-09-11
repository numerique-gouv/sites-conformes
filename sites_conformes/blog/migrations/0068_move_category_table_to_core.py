from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sites_conformes_blog", "0067_alter_blogentrypage_body_alter_blogindexpage_body_and_more"),
        ("sites_conformes_events", "0039_alter_evententrypage_body_alter_eventsindexpage_body"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterModelTable(name="category", table="sites_conformes_core_category"),
            ],
        ),
    ]
