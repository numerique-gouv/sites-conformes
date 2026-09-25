from django.contrib import messages
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.views import View
from treebeard.exceptions import InvalidMoveToDescendant
from wagtail.admin.auth import permission_denied
from wagtail.snippets.views.snippets import IndexView, SnippetViewSet

from sites_conformes.core.models import Category


class CategoryIndexView(IndexView):
    """Lists the categories as a nested tree with drag-and-drop; search and sorting fall back to the flat table."""

    move_url_name = None

    @cached_property
    def is_tree_mode(self) -> bool:
        return not (self.is_searching or self.is_filtering or self.is_explicitly_ordered)

    def get_paginate_by(self, queryset):
        return None if self.is_tree_mode else super().get_paginate_by(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.is_tree_mode:
            roots = Category.get_root_nodes()
            if self.locale:
                roots = roots.filter(locale=self.locale)
            context["tree_roots"] = roots
            context["move_url"] = reverse(self.move_url_name)
        return context


class CategoryMoveView(View):
    """Re-parents a category: POST ``node`` and ``target`` (a category pk), or ``node`` alone to make it a root."""

    permission_policy = None

    def post(self, request):
        if not self.permission_policy.user_has_permission(request.user, "change"):
            return permission_denied(request)
        node = get_object_or_404(Category, pk=request.POST.get("node"))
        target_pk = request.POST.get("target")
        try:
            if target_pk:
                target = get_object_or_404(Category, pk=target_pk)
                node.move(target, pos="sorted-child")
                messages.success(
                    request, _("Category “%(node)s” moved under “%(target)s”.") % {"node": node, "target": target}
                )
            else:
                node.move(Category.get_first_root_node(), pos="sorted-sibling")
                messages.success(request, _("Category “%(node)s” moved to the root.") % {"node": node})
        except InvalidMoveToDescendant:
            error = _("A category cannot be moved under itself or one of its sub-categories.")
            messages.error(request, error)
            return HttpResponseBadRequest(error)
        return JsonResponse({"ok": True})


class CategoryViewSet(SnippetViewSet):
    model = Category
    icon = "tag"  # type: ignore
    index_view_class = CategoryIndexView
    index_template_name = "sites_conformes_core/admin/category_index.html"
    index_results_template_name = "sites_conformes_core/admin/category_index_results.html"
    list_display = ["name", "parent"]
    search_fields = ["name"]

    def get_index_view_kwargs(self, **kwargs):
        return super().get_index_view_kwargs(move_url_name=self.get_url_name("move"), **kwargs)

    def get_urlpatterns(self):
        return super().get_urlpatterns() + [path("move/", self.move_view, name="move")]

    @property
    def move_view(self):
        return CategoryMoveView.as_view(permission_policy=self.permission_policy)
