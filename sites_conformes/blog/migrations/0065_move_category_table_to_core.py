from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("sites_conformes_blog", "0064_recent_events_block__see_all_events_link"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterModelTable(name="category", table="sites_conformes_core_category"),
            ],
        ),
    ]
