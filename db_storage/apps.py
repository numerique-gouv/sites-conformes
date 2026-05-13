from django.apps import AppConfig


class DbStorageConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sites_conformes.db_storage"
    label = "sites_conformes_db_storage"
