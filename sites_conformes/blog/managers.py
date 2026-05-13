from django.db import models


class CategoryManager(models.Manager):
    def with_uses(self, blog_page):
        entries = blog_page.get_entries()
        return self.filter(entrypage__in=entries).distinct()
