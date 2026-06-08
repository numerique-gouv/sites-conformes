from django.apps import AppConfig


class PublicationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "publications"
    label = "publications"

    def ready(self):
        from config.api import api_router

        from publications.api import CollectionsAPIViewSet, ThemesAPIViewSet

        api_router.register_endpoint("collections", CollectionsAPIViewSet)
        api_router.register_endpoint("themes", ThemesAPIViewSet)
