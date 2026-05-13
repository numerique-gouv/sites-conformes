import uuid

import django.db.models.deletion
from django.db import migrations, models


def set_unique_translation_keys(apps, _schema_editor):
    FormField = apps.get_model("sites_conformes_forms", "FormField")
    for ff in FormField.objects.all():
        ff.translation_key = uuid.uuid4()
        ff.save(update_fields=["translation_key"])


def set_default_locale(apps, _schema_editor):
    FormField = apps.get_model("sites_conformes_forms", "FormField")
    Locale = apps.get_model("wagtailcore", "Locale")
    default_locale = Locale.objects.filter(language_code="fr").first() or Locale.objects.first()
    if default_locale:
        FormField.objects.filter(locale__isnull=True).update(locale=default_locale)


class Migration(migrations.Migration):

    dependencies = [
        ("sites_conformes_forms", "0003_formpage_honeypot"),
        ("wagtailcore", "0096_referenceindex_referenceindex_source_object_and_more"),
    ]

    operations = [
        # Add translation_key as nullable first so existing rows can be populated
        migrations.AddField(
            model_name="formfield",
            name="translation_key",
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        # Populate unique UUIDs for each existing row
        migrations.RunPython(set_unique_translation_keys, reverse_code=migrations.RunPython.noop),
        # Make translation_key non-nullable
        migrations.AlterField(
            model_name="formfield",
            name="translation_key",
            field=models.UUIDField(default=uuid.uuid4, editable=False),
        ),
        # Add locale as nullable first
        migrations.AddField(
            model_name="formfield",
            name="locale",
            field=models.ForeignKey(
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="wagtailcore.locale",
                verbose_name="locale",
            ),
        ),
        # Set locale for existing rows from their parent FormPage's locale
        migrations.RunSQL(
            sql="""
                UPDATE sites_conformes_forms_formfield ff
                SET locale_id = wp.locale_id
                FROM sites_conformes_forms_formpage fp
                JOIN wagtailcore_page wp ON wp.id = fp.page_ptr_id
                WHERE fp.page_ptr_id = ff.page_id
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Fallback: set remaining null locales to the default locale
        migrations.RunPython(set_default_locale, reverse_code=migrations.RunPython.noop),
        # Make locale non-nullable
        migrations.AlterField(
            model_name="formfield",
            name="locale",
            field=models.ForeignKey(
                editable=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="wagtailcore.locale",
                verbose_name="locale",
            ),
        ),
        # Add the unique constraint
        migrations.AlterUniqueTogether(
            name="formfield",
            unique_together={("translation_key", "locale")},
        ),
    ]
