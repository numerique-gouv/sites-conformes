from django.db import models
from django.db.models import Count, Q

from sites_conformes.core import get_contentpage_model


class TagManager(models.Manager):
    """
    Custom manager for Tag model.

    Add a method to get tags with a minimum use count on live pages only.
    """

    def tags_with_usecount(self, min_count=0):
        # Reverse name of the through model's ``tag`` key (``<app>_<through>_items``),
        # which follows the swappable content page model.
        through = get_contentpage_model()._meta.get_field("tags").remote_field.through
        items = through._meta.get_field("tag").related_query_name()
        return self.annotate(
            usecount=Count(items, filter=Q(**{f"{items}__content_object__live": True}), distinct=True)
        ).filter(usecount__gte=min_count)
