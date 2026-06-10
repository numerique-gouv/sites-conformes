from django.apps import AppConfig


class TestAppConfig(AppConfig):
    """
    App holding test-only models (e.g. a custom content page model).
    Only installed by config.settings_test, never in production.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "sites_conformes.testapp"
    label = "sites_conformes_testapp"
