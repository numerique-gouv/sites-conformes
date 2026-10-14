"""Category filters of the catalog, walked over the category tree held in memory."""

from collections import defaultdict
from dataclasses import dataclass

from django.db import models


@dataclass(frozen=True)
class FilterChip:
    category: models.Model
    checked: bool
    # Ancestors and self as "/1/4/", so unticking a category can untick everything below it in the form.
    path: str


class CategoryFilters:
    """
    One group of filters per parent category: its subcategories, shown straight away.

    The groups are the parent categories chosen on the page, or else every root category in use
    that has subcategories in use; root categories without any are offered together in a last group.
    Like the tags, they follow the selection mode of the page: one category at a time, or several
    combined with its operator (match any, or match all).
    Ticking a category matches the pages of its whole branch and shows its own subcategories,
    so the choice can be narrowed: a ticked subcategory then replaces its parent in the filter.
    """

    def __init__(self, categories, used_ids, selected_slugs, group_ids=None, single=False, match_all=False):
        self.match_all = match_all
        # ponytail: the whole tree is loaded at once, fine for the few hundred categories a site has.
        self.by_id = {c.pk: c for c in categories}
        self.children = defaultdict(list)
        for category in categories:
            self.children[category.parent_id].append(category)

        self.visible_ids = set()
        for category_id in used_ids:
            self.visible_ids.update(c.pk for c in self.ancestors(self.by_id.get(category_id)))

        visible = [c for c in self.walk(self.children[None]) if c.pk in self.visible_ids]
        if group_ids:
            # Only root categories can be groups; a subcategory chosen before that rule is left out.
            self.heads = [c for c in visible if c.pk in set(group_ids) and c.parent_id is None]
            self.loose = []
        else:
            roots = [c for c in visible if c.parent_id is None]
            self.heads = [c for c in roots if self.visible_children(c)]
            self.loose = [c for c in roots if not self.visible_children(c)]
        self.head_ids = {c.pk for c in self.heads}

        self.selected_ids = set()
        for category in categories:
            if category.slug in selected_slugs and self.is_selectable(category):
                # A link to a subcategory alone also ticks its parents, so its branch opens.
                self.selected_ids.update(c.pk for c in self.ancestors(category) if self.is_selectable(c))
        if single and self.current:
            self.selected_ids = {c.pk for c in self.ancestors(self.current[0]) if self.is_selectable(c)}

    def walk(self, categories):
        """Depth-first, in sibling order."""
        for category in categories:
            yield category
            yield from self.walk(self.children[category.pk])

    def ancestors(self, category):
        """The category and its parents, from the category up."""
        seen = set()
        while category is not None and category.pk not in seen:
            seen.add(category.pk)
            yield category
            category = self.by_id.get(category.parent_id)

    def visible_children(self, category) -> list:
        return [c for c in self.children[category.pk] if c.pk in self.visible_ids]

    def group_of(self, category):
        """The group heading above the category, or None for the root categories offered on their own."""
        return next((c for c in list(self.ancestors(category))[1:] if c.pk in self.head_ids), None)

    def is_selectable(self, category) -> bool:
        return category in self.loose or self.group_of(category) is not None

    @property
    def has_filters(self) -> bool:
        return bool(self.heads or self.loose)

    @property
    def selected(self) -> list:
        """Every ticked category, the implied parents included: what the filter form submits."""
        return [c for c in self.walk(self.children[None]) if c.pk in self.selected_ids]

    @property
    def current(self) -> list:
        """The most specific ticked categories: a ticked subcategory narrows its parent."""
        return [c for c in self.selected if not any(child.pk in self.selected_ids for child in self.children[c.pk])]

    def filter(self, entries: models.QuerySet) -> models.QuerySet:
        branches = [{c.pk for c in self.walk([category])} for category in self.current]
        if not branches:
            return entries
        if self.match_all:
            for ids in branches:
                # One join per category: chained filters on a many-to-many are ANDed.
                entries = entries.filter(categories__in=ids)
        else:
            entries = entries.filter(categories__in=set().union(*branches))
        return entries.distinct()

    def chips(self, categories) -> list[FilterChip]:
        return [
            FilterChip(
                c,
                c.pk in self.selected_ids,
                "/" + "/".join(str(a.pk) for a in reversed(list(self.ancestors(c)))) + "/",
            )
            for c in categories
        ]

    @property
    def rows(self) -> list[tuple[models.Model | None, list[FilterChip]]]:
        """(heading, chips): each group, followed by the subcategories of its ticked categories."""
        rows = []
        for head in self.heads:
            rows.append((head, self.chips(self.visible_children(head))))
            for category in self.walk(self.visible_children(head)):
                if category.pk in self.selected_ids and self.visible_children(category):
                    rows.append((category, self.chips(self.visible_children(category))))
        if self.loose:
            rows.append((None, self.chips(self.loose)))
        return rows
