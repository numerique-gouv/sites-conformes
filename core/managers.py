from django.db import models
from django.db.models import Count, Q


class TagManager(models.Manager):
    """
    Custom manager for Tag model.

    Add a method to get tags with a minimum use count on live pages only.
    """

    def tags_with_usecount(self, min_count=0):
        return self.annotate(
            usecount=Count(
                "content_manager_tagcontentpage_items",
                filter=Q(content_manager_tagcontentpage_items__content_object__live=True),
                distinct=True,
            )
        ).filter(usecount__gte=min_count)
