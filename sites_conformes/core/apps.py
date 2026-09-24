from django.apps import AppConfig


class ContentManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sites_conformes.core"
    label = "sites_conformes_core"

    # Monkey patches are applied in the ready() method of the AppConfig, which is called when the app is loaded.
    # This ensures that the patches are applied before any code that relies on the patched behavior is executed.
    # To be removed once wagtail-localize fixes the bug in handle_image_block (https://github.com/wagtail/wagtail-localize/pull/935)
    def ready(self):
        from .monkey_patches import patch_wagtail_localize_handle_image_block

        patch_wagtail_localize_handle_image_block()

        # Wagtail (< 8.1) registers every concrete page class, including one swapped out
        # via Meta.swappable, which would keep it creatable in the admin.
        from wagtail.models import PAGE_MODEL_CLASSES

        PAGE_MODEL_CLASSES[:] = [model for model in PAGE_MODEL_CLASSES if not model._meta.swapped]
