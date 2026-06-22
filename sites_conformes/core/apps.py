from django.apps import AppConfig


class ContentManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sites_conformes.core"
    label = "sites_conformes_core"

    def ready(self):
        from .monkey_patches import patch_wagtail_localize_handle_image_block

        patch_wagtail_localize_handle_image_block()
