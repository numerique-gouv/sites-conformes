from django.db.models import Case, When
from django.utils.functional import cached_property
from wagtail.snippets.views.snippets import IndexView, SnippetViewSet

from sites_conformes.core.models import Category

TREE_CELL_TEMPLATE = "sites_conformes_core/admin/category_title_cell.html"


class CategoryIndexView(IndexView):
    """Lists the categories as a tree: every child follows its parent, indented."""

    def order_queryset(self, queryset):
        if self.is_searching or self.is_explicitly_ordered:
            return super().order_queryset(queryset)

        ordered_pks = [category.pk for category in Category.in_tree_order(queryset)]
        if not ordered_pks:
            return queryset
        position = Case(*[When(pk=pk, then=index) for index, pk in enumerate(ordered_pks)])
        return queryset.order_by(position)

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
