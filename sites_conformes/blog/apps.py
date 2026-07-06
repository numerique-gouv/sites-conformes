from django.apps import AppConfig


class BlogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sites_conformes.blog"
    label = "sites_conformes_blog"

    def ready(self):
        from sites_conformes.blog.models import BlogEntryPage
        from sites_conformes.blog.taxonomies import CATEGORY
        from sites_conformes.blog.taxonomy import register_taxonomies

        register_taxonomies(BlogEntryPage, [CATEGORY])
