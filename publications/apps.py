from django.apps import AppConfig


class PublicationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "publications"
    label = "publications"

    def ready(self):
        from config.api import api_router
        from publications.api import CollectionsAPIViewSet, ThemesAPIViewSet
        from publications.blocks.register_sites_conformes_blocks import register_sites_conformes_blocks

        # Inject publication StreamField blocks into Sites Conformes page types at
        # startup (skipped during makemigrations — see register_sites_conformes_blocks).
        register_sites_conformes_blocks()

        api_router.register_endpoint("collections", CollectionsAPIViewSet)
        api_router.register_endpoint("themes", ThemesAPIViewSet)

        from publications.models import PublicationPage
        from publications.taxonomies import COLLECTION, THEME
        from sites_conformes.blog.taxonomy import register_taxonomies

        register_taxonomies(PublicationPage, [COLLECTION, THEME])
