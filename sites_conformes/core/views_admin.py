from django.db.models import Case, When
from django.utils.functional import cached_property
from wagtail.snippets.views.snippets import IndexView, SnippetViewSet

from sites_conformes.core.models import Category

TREE_CELL_TEMPLATE = "sites_conformes_core/admin/category_title_cell.html"


class CategoryIndexView(IndexView):
    """Lists the categories as a tree: every child follows its parent, indented by depth."""

    def order_queryset(self, queryset):
        if self.is_searching or self.is_explicitly_ordered:
            return super().order_queryset(queryset)

        # ponytail: get_tree() queries once per non-leaf category, fine for the few dozen a site has.
        tree = Category.get_tree()
        if not tree:
            return queryset
        position = Case(*[When(pk=node.pk, then=index) for index, node in enumerate(tree)])
        depth = Case(*[When(pk=node.pk, then=node.get_depth() - 1) for node in tree])
        return queryset.annotate(tree_depth=depth).order_by(position)

    @cached_property
    def columns(self):
        columns = super().columns
        if not (self.is_searching or self.is_explicitly_ordered):
            for column in columns:
                if column.name == "name":
                    column.cell_template_name = TREE_CELL_TEMPLATE
        return columns


class CategoryViewSet(SnippetViewSet):
    model = Category
    icon = "tag"  # type: ignore
    index_view_class = CategoryIndexView
    list_display = ["name", "parent"]
    search_fields = ["name"]
