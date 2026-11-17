from django.db import migrations


def _get_model(apps, app_label, model_name):
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def forwards_delete_legacy_menu_entries(apps, schema_editor):
    """Delete the entries of the obsolete wagtailmenus app.

    Their content was converted to the new menus by 0002_migrate_from_legacy_menus.
    The legacy mega menus (sites_conformes_core.MegaMenu*) are deleted in cascade.
    """
    for model_name in ("FlatMenuItem", "FlatMenu", "MainMenuItem", "MainMenu"):
        model = _get_model(apps, "wagtailmenus", model_name)
        if model is not None:
            model.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("sites_conformes_menus", "0003_alter_footerbottommenu_unique_together_and_more"),
        ("wagtailmenus", "0023_remove_use_specific"),
    ]

    operations = [
        migrations.RunPython(forwards_delete_legacy_menu_entries, migrations.RunPython.noop),
    ]
