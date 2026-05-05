from django.db import migrations

from wagtail.contrib.forms.utils import get_field_clean_name


def fix_empty_clean_names(apps, schema_editor):
    FormField = apps.get_model("forms", "FormField")
    for field in FormField.objects.filter(clean_name=""):
        field.clean_name = get_field_clean_name(field.label)
        field.save(update_fields=["clean_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("forms", "0004_formfield_locale_formfield_translation_key_and_more"),
    ]

    operations = [
        migrations.RunPython(fix_empty_clean_names, reverse_code=migrations.RunPython.noop),
    ]
