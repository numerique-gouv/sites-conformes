from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"  # type: ignore
    name = "sites_conformes.dashboard"
    label = "sites_conformes_dashboard"

    # Monkey patches are applied in the ready() method of the AppConfig, which is called when the app is loaded.
    # This ensures that the patches are applied before any code that relies on the patched behavior is executed.
    # To be removed once wagtail-2fa fixes the "delete + recreate unconfirmed device on every GET" bug
    # (see monkey_patches.py for details) and the dependency is upgraded past the fixed version.
    def ready(self):
        from sites_conformes.dashboard.monkey_patches import patch_wagtail_2fa_new_unconfirmed_device

        patch_wagtail_2fa_new_unconfirmed_device()
