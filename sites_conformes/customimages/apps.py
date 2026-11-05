from django.apps import AppConfig


class CustomimagesConfig(AppConfig):
    name = "sites_conformes.customimages"
    label = "sites_conformes_customimages"
    # Its migrations were created with AutoField: keep it whatever DEFAULT_AUTO_FIELD the host project sets.
    default_auto_field = "django.db.models.AutoField"
