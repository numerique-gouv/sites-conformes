"""
Migrate Wagtail blog pages to the publications app.

Glossary
--------
ContentType
    Django model (``django.contrib.contenttypes``) that records which model class
    each row “is”. ``wagtailcore_page.content_type`` tells Wagtail whether a page
    is a ``BlogEntryPage``, ``PublicationPage``, etc. Promoting a page updates this
    pointer and adds a row in the child table (``publications_publicationpage``).

Primary keys
    ``PublicationPage`` subclasses ``BlogEntryPage`` via multi-table inheritance.
    The publication row uses ``blogentrypage_ptr_id`` as its primary key, which is
    the same value as the existing ``BlogEntryPage`` / ``wagtailcore_page`` id.
    URLs, tree position, revisions, tags, and authors are unchanged.

Phases (run separately, in order)
    Each phase runs inside a single database transaction (``run_phase``). If a
    phase raises, all of its writes are rolled back; phases do not share a
    transaction, so a completed phase 1 is kept if phase 2 fails later.

    1. ``migrate_pages`` — promote ``BlogIndexPage`` / ``BlogEntryPage`` instances
       to ``PublicationIndexPage`` / ``PublicationPage``.
    2. ``create_taxonomies`` — create ``Collection`` / ``Theme`` snippets from
       descendants of the blog categories “Collections” and “Thématiques”.
    3. ``assign_taxonomies`` — link publications to new taxonomies from their
       former ``blog_categories``.

Operations
    Consider disabling or hiding the Wagtail admin (maintenance mode, IP allowlist,
    Scalingo maintenance page, etc.) while the data migration runs, so editors do
    not create or edit pages concurrently with type promotion.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

MIGRATION_LOG_OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def migration_log_path(
    *,
    override: Path | str | None = None,
    started_at=None,
) -> Path:
    """Return a log file path for one command run (new file per invocation)."""
    if override is not None:
        return Path(override)
    started_at = started_at or timezone.now()
    stamp = started_at.strftime("%Y-%m-%dT%H-%M-%S")
    MIGRATION_LOG_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return MIGRATION_LOG_OUTPUT_DIR / f"migrate_blog_to_publications_{stamp}.log"


@dataclass
class MigrationConfig:
    """Adjust for the site being migrated."""

    # If set, only these blog index slugs are migrated; if empty, all BlogIndexPages are.
    blog_index_slugs: list[str] = field(default_factory=list)

    # Wagtail language code (e.g. ``fr``) used for slug lookups; default site locale if unset.
    locale_language_code: str | None = None

    # Root blog categories: only their children and grandchildren are migrated.
    collections_root_names: tuple[str, ...] = ("Collections",)
    collections_root_slugs: tuple[str, ...] = ("collections",)
    themes_root_names: tuple[str, ...] = ("Thématiques",)
    themes_root_slugs: tuple[str, ...] = ("thematiques",)


class LogWriter(Protocol):
    def __call__(self, line: str) -> None: ...


@dataclass
class MigrationReport:
    phase: str
    dry_run: bool
    messages: list[str] = field(default_factory=list)
    log_file: TextIO | None = None
    log_stdout: LogWriter | None = None

    def log(self, message: str) -> None:
        prefix = "[dry-run] " if self.dry_run else ""
        line = f"{prefix}{message}"
        self.messages.append(line)
        if self.log_stdout is not None:
            self.log_stdout(line)
        else:
            print(line, flush=True)
        if self.log_file is not None:
            self.log_file.write(line + "\n")
            self.log_file.flush()


def _migration_report(
    phase: str,
    *,
    dry_run: bool,
    log_file: TextIO | None,
    log_stdout: LogWriter | None,
) -> MigrationReport:
    return MigrationReport(
        phase=phase,
        dry_run=dry_run,
        log_file=log_file,
        log_stdout=log_stdout,
    )


def resolve_migration_locale(config: MigrationConfig):
    """Locale used for slug-based lookups (blog indexes, category roots)."""
    from wagtail.models import Locale

    if config.locale_language_code:
        return Locale.objects.get(language_code=config.locale_language_code)
    locale = (
        Locale.get_default()
        or Locale.objects.filter(language_code="fr").first()
        or Locale.objects.first()
    )
    if locale is None:
        raise Locale.DoesNotExist("no locales configured")
    return locale


def _get_blog_index_by_slug(slug: str, locale):
    from sites_conformes.blog.models import BlogIndexPage

    return BlogIndexPage.objects.get(slug=slug, locale=locale)


def _get_blog_indexes(config: MigrationConfig, report: MigrationReport):
    from sites_conformes.blog.models import BlogIndexPage

    if config.blog_index_slugs:
        locale = resolve_migration_locale(config)
        indexes = []
        for slug in config.blog_index_slugs:
            try:
                indexes.append(_get_blog_index_by_slug(slug, locale))
            except BlogIndexPage.DoesNotExist:
                report.log(
                    f"Blog index with slug '{slug}' (locale={locale.language_code}) not found — skipped.",
                )
        return indexes
    return list(BlogIndexPage.objects.all())


def blog_index_scope_label(config: MigrationConfig) -> str:
    if config.blog_index_slugs:
        locale = resolve_migration_locale(config)
        slugs = ", ".join(config.blog_index_slugs)
        return f"{slugs} (locale={locale.language_code})"
    return "all BlogIndexPage(s)"


@dataclass
class BlogIndexSummary:
    slug: str
    found: bool
    title: str | None = None
    pk: int | None = None
    entry_count: int | None = None
    locale_language_code: str | None = None


@dataclass
class TaxonomyMigrationSummary:
    collections_root_name: str | None
    collections_root_pk: int | None
    collections_category_count: int
    themes_root_name: str | None
    themes_root_pk: int | None
    themes_category_count: int


@dataclass
class AssignTaxonomiesSummary:
    collection_count: int
    theme_count: int


@dataclass
class AssignTaxonomyIndexScope:
    slug: str
    found: bool
    title: str | None = None
    pk: int | None = None
    locale_language_code: str | None = None
    post_count: int = 0


def get_blog_index_summaries(config: MigrationConfig) -> list[BlogIndexSummary]:
    """Indexes selected by ``config`` and how many blog entries each contains."""
    from sites_conformes.blog.models import BlogEntryPage, BlogIndexPage

    if config.blog_index_slugs:
        locale = resolve_migration_locale(config)
        summaries = []
        for slug in config.blog_index_slugs:
            try:
                index = _get_blog_index_by_slug(slug, locale)
            except BlogIndexPage.DoesNotExist:
                summaries.append(
                    BlogIndexSummary(
                        slug=slug,
                        found=False,
                        locale_language_code=locale.language_code,
                    ),
                )
                continue
            summaries.append(
                BlogIndexSummary(
                    slug=slug,
                    found=True,
                    title=index.title,
                    pk=index.pk,
                    entry_count=BlogEntryPage.objects.child_of(index).count(),
                    locale_language_code=locale.language_code,
                ),
            )
        return summaries

    return [
        BlogIndexSummary(
            slug=index.slug,
            found=True,
            title=index.title,
            pk=index.pk,
            entry_count=BlogEntryPage.objects.child_of(index).count(),
            locale_language_code=index.locale.language_code,
        )
        for index in BlogIndexPage.objects.all().order_by("slug")
    ]


def format_blog_index_summaries(summaries: list[BlogIndexSummary]) -> list[str]:
    lines = ["Blog indexes in scope:"]
    if not summaries:
        lines.append("  (none)")
        return lines
    for summary in summaries:
        if not summary.found:
            locale_label = f", locale={summary.locale_language_code}" if summary.locale_language_code else ""
            lines.append(f"  - slug '{summary.slug}' NOT FOUND{locale_label}")
            continue
        entry_label = "entry" if summary.entry_count == 1 else "entries"
        lines.append(
            f'  - "{summary.title}" (slug={summary.slug}, pk={summary.pk}): '
            f"{summary.entry_count} {entry_label}",
        )
    return lines


def get_taxonomy_migration_summary(config: MigrationConfig) -> TaxonomyMigrationSummary:
    """Category roots and how many blog categories phase 2 would migrate."""
    locale = resolve_migration_locale(config)
    collections_root = _find_root_category(
        config.collections_root_names,
        config.collections_root_slugs,
        locale=locale,
    )
    themes_root = _find_root_category(
        config.themes_root_names,
        config.themes_root_slugs,
        locale=locale,
    )
    return TaxonomyMigrationSummary(
        collections_root_name=collections_root.name if collections_root else None,
        collections_root_pk=collections_root.pk if collections_root else None,
        collections_category_count=(
            len(_descendants_two_levels(collections_root)) if collections_root else 0
        ),
        themes_root_name=themes_root.name if themes_root else None,
        themes_root_pk=themes_root.pk if themes_root else None,
        themes_category_count=len(_descendants_two_levels(themes_root)) if themes_root else 0,
    )


def format_taxonomy_migration_summary(summary: TaxonomyMigrationSummary) -> list[str]:
    lines = ["Taxonomy migration (phase 2):"]
    if summary.collections_root_name:
        lines.append(
            f"  - Collections root: '{summary.collections_root_name}' "
            f"(pk={summary.collections_root_pk}): "
            f"{summary.collections_category_count} categor"
            f"{'y' if summary.collections_category_count == 1 else 'ies'} to migrate",
        )
    else:
        lines.append("  - Collections root: NOT FOUND")

    if summary.themes_root_name:
        lines.append(
            f"  - Themes root: '{summary.themes_root_name}' "
            f"(pk={summary.themes_root_pk}): "
            f"{summary.themes_category_count} categor"
            f"{'y' if summary.themes_category_count == 1 else 'ies'} to migrate",
        )
    else:
        lines.append("  - Themes root: NOT FOUND")
    return lines


def get_assign_taxonomies_summary(_config: MigrationConfig) -> AssignTaxonomiesSummary:
    """Collection and theme snippet counts available for phase 3 assignment."""
    from publications.models import Collection, Theme

    return AssignTaxonomiesSummary(
        collection_count=Collection.objects.count(),
        theme_count=Theme.objects.count(),
    )


def format_assign_taxonomies_summary(summary: AssignTaxonomiesSummary) -> list[str]:
    collection_label = "Collection" if summary.collection_count == 1 else "Collections"
    theme_label = "Theme" if summary.theme_count == 1 else "Themes"
    return [
        "Taxonomy assignment (phase 3):",
        f"  - {summary.collection_count} {collection_label}",
        f"  - {summary.theme_count} {theme_label}",
    ]


def get_assign_taxonomies_scope(config: MigrationConfig) -> list[AssignTaxonomyIndexScope]:
    """Publication indexes and posts phase 3 would assign collections/themes on."""
    from publications.models import PublicationPage
    from sites_conformes.blog.models import BlogIndexPage

    def scope_for_index(index) -> AssignTaxonomyIndexScope:
        return AssignTaxonomyIndexScope(
            slug=index.slug,
            found=True,
            title=index.title,
            pk=index.pk,
            locale_language_code=index.locale.language_code,
            post_count=PublicationPage.objects.child_of(index).count(),
        )

    if config.blog_index_slugs:
        locale = resolve_migration_locale(config)
        scopes = []
        for slug in config.blog_index_slugs:
            try:
                index = _get_blog_index_by_slug(slug, locale)
            except BlogIndexPage.DoesNotExist:
                scopes.append(
                    AssignTaxonomyIndexScope(
                        slug=slug,
                        found=False,
                        locale_language_code=locale.language_code,
                    ),
                )
                continue
            scopes.append(scope_for_index(index))
        return scopes

    return [scope_for_index(index) for index in BlogIndexPage.objects.all().order_by("slug")]


def format_assign_taxonomies_scope(scopes: list[AssignTaxonomyIndexScope]) -> list[str]:
    lines = ["Publication indexes and posts in scope:"]
    if not scopes:
        lines.append("  (none)")
        return lines

    for scope in scopes:
        if not scope.found:
            locale_label = f", locale={scope.locale_language_code}" if scope.locale_language_code else ""
            lines.append(f"  - slug '{scope.slug}' NOT FOUND{locale_label}")
            continue

        post_label = "post" if scope.post_count == 1 else "posts"
        lines.append(
            f'  - "{scope.title}" (slug={scope.slug}, pk={scope.pk}): '
            f"{scope.post_count} {post_label}",
        )

    return lines


def _promote_page_to_child_model(page, child_model, *, content_type) -> None:
    """
    Add an MTI child-table row and point ``wagtailcore_page.content_type`` at ``child_model``.

    Uses ``save_base(raw=True)`` so Django inserts only the child table row without
    calling ``Page.save()`` / ``full_clean()`` (see Django MTI downcast workarounds).
    """
    from wagtail.models import Page

    if child_model.objects.filter(pk=page.pk).exists():
        Page.objects.filter(pk=page.pk).update(content_type=content_type)
        return

    parent_model = next(iter(child_model._meta.parents))
    ptr_field = child_model._meta.parents[parent_model]
    child = child_model(**{ptr_field.attname: page.pk})
    child.save_base(raw=True, force_insert=True)
    Page.objects.filter(pk=page.pk).update(content_type=content_type)


def migrate_pages(
    config: MigrationConfig,
    *,
    dry_run: bool = False,
    log_file: TextIO | None = None,
    log_stdout: LogWriter | None = None,
) -> MigrationReport:
    """
    Phase 1 — Promote blog index and entry pages to publication types.

    Inserts rows in ``publications_publicationindexpage`` /
    ``publications_publicationpage`` and updates ``content_type`` on
    ``wagtailcore_page``. Does not touch categories, collections, or stream JSON.
    """
    from publications.models import PublicationIndexPage, PublicationPage
    from sites_conformes.blog.models import BlogEntryPage, BlogIndexPage

    report = _migration_report(
        "1-migrate_pages",
        dry_run=dry_run,
        log_file=log_file,
        log_stdout=log_stdout,
    )
    index_ct = ContentType.objects.get_for_model(PublicationIndexPage)
    entry_ct = ContentType.objects.get_for_model(PublicationPage)

    for index in _get_blog_indexes(config, report):
        slug = index.slug
        if isinstance(index.specific, PublicationIndexPage):
            report.log(f"Index '{slug}' (pk={index.pk}) is already a PublicationIndexPage.")
        else:
            report.log(f"Promoting index '{index.title}' (pk={index.pk}, slug={slug}).")
            if not dry_run:
                _promote_page_to_child_model(
                    index,
                    PublicationIndexPage,
                    content_type=index_ct,
                )

        entries = BlogEntryPage.objects.child_of(index).specific()
        for entry in entries:
            if isinstance(entry, PublicationPage):
                report.log(f"  Entry pk={entry.pk} already PublicationPage — skipped.")
                continue
            report.log(f"  Promoting entry '{entry.title}' (pk={entry.pk}).")
            if not dry_run:
                _promote_page_to_child_model(
                    entry,
                    PublicationPage,
                    content_type=entry_ct,
                )

    return report


def _find_root_category(
    names: tuple[str, ...],
    slugs: tuple[str, ...],
    *,
    locale,
):
    from django.db.models import Q
    from sites_conformes.blog.models import Category

    return Category.objects.filter(
        Q(name__in=names) | Q(slug__in=slugs),
        locale=locale,
    ).first()


def _descendants_two_levels(root):
    """Children and grandchildren of ``root`` (root itself is excluded)."""
    from sites_conformes.blog.models import Category

    children = list(Category.objects.filter(parent=root).order_by("name"))
    grandchildren = list(
        Category.objects.filter(parent__in=children).order_by("name"),
    )
    return children + grandchildren


def create_taxonomies(
    config: MigrationConfig,
    *,
    dry_run: bool = False,
    log_file: TextIO | None = None,
    log_stdout: LogWriter | None = None,
) -> MigrationReport:
    """
    Phase 2 — Create ``Collection`` / ``Theme`` snippets from blog categories.

    Only categories that are children or grandchildren of the roots
    “Collections” / “Thématiques” are copied. Slugs are preserved so phase 3 can
    match ``blog_categories`` to the new snippets.
    """
    from publications.models import Collection, Theme

    report = _migration_report(
        "2-create_taxonomies",
        dry_run=dry_run,
        log_file=log_file,
        log_stdout=log_stdout,
    )

    locale = resolve_migration_locale(config)
    collections_root = _find_root_category(
        config.collections_root_names,
        config.collections_root_slugs,
        locale=locale,
    )
    if not collections_root:
        report.log(
            f"Root category for collections not found (locale={locale.language_code}) "
            "— no collections created.",
        )
    else:
        report.log(
            f"Collections root: '{collections_root.name}' (pk={collections_root.pk}).",
        )
        _create_taxonomies_from_categories(
            _descendants_two_levels(collections_root),
            Collection,
            report,
            dry_run=dry_run,
        )

    themes_root = _find_root_category(
        config.themes_root_names,
        config.themes_root_slugs,
        locale=locale,
    )
    if not themes_root:
        report.log(
            f"Root category for themes not found (locale={locale.language_code}) — no themes created.",
        )
    else:
        report.log(f"Themes root: '{themes_root.name}' (pk={themes_root.pk}).")
        _create_taxonomies_from_categories(
            _descendants_two_levels(themes_root),
            Theme,
            report,
            dry_run=dry_run,
        )

    return report


def _create_taxonomies_from_categories(categories, model, report: MigrationReport, *, dry_run: bool):
    """Create Collection or Theme rows, preserving slug and locale."""
    slug_to_instance: dict[str, object] = {}

    category_pks = {category.pk for category in categories}
    # Children of the root first, then grandchildren.
    categories = sorted(
        categories,
        key=lambda category: (category.parent_id in category_pks, category.name),
    )
    for category in categories:
        if model.objects.filter(slug=category.slug, locale=category.locale).exists():
            report.log(f"  {model.__name__} slug='{category.slug}' already exists — skipped.")
            slug_to_instance[category.slug] = model.objects.get(
                slug=category.slug,
                locale=category.locale,
            )
            continue

        report.log(f"  Create {model.__name__} '{category.name}' (slug={category.slug}).")
        if dry_run:
            continue

        instance = model(
            name=category.name,
            slug=category.slug,
            description=category.description,
            colophon=category.colophon,
            locale=category.locale,
            translation_key=category.translation_key,
        )
        instance.save()
        slug_to_instance[category.slug] = instance

    if dry_run:
        return

    # Second pass: wire parent FKs using the same slugs as the source tree.
    for category in categories:
        if not category.parent_id:
            continue
        parent_slug = category.parent.slug
        child = model.objects.filter(slug=category.slug, locale=category.locale).first()
        parent = model.objects.filter(slug=parent_slug, locale=category.locale).first()
        if child and parent and child.parent_id != parent.pk:
            child.parent = parent
            child.save(update_fields=["parent"])


def _migrated_category_slugs():
    from publications.models import Collection, Theme

    collection_slugs = set(Collection.objects.values_list("slug", flat=True))
    theme_slugs = set(Theme.objects.values_list("slug", flat=True))
    return collection_slugs, theme_slugs, collection_slugs | theme_slugs


def assign_taxonomies(
    config: MigrationConfig,
    *,
    dry_run: bool = False,
    log_file: TextIO | None = None,
    log_stdout: LogWriter | None = None,
) -> MigrationReport:
    """
    Phase 3 — Assign collections/themes to publications.

    For each ``PublicationPage`` under the selected indexes (all by default), each
    ``blog_categories`` entry is matched by slug to exactly one ``Collection`` or
    ``Theme`` from phase 2. Ambiguous or missing matches raise ``ValueError``;
    existing assignments are logged and left unchanged.
    """
    from publications.models import PublicationPage

    report = _migration_report(
        "3-assign_taxonomies",
        dry_run=dry_run,
        log_file=log_file,
        log_stdout=log_stdout,
    )

    collection_slugs, theme_slugs, migrated_category_slugs = _migrated_category_slugs()

    if not migrated_category_slugs:
        report.log("No collections/themes in database — run phase 2 first.")

    for index in _get_blog_indexes(config, report):
        for post in PublicationPage.objects.child_of(index):
            _assign_post_taxonomies(post, collection_slugs, theme_slugs, report, dry_run=dry_run)

    return report


def _assign_post_taxonomies(post, collection_slugs, theme_slugs, report: MigrationReport, *, dry_run: bool):
    from publications.models import Collection, Theme

    changed = False
    for category in post.blog_categories.all():
        in_collections = category.slug in collection_slugs
        in_themes = category.slug in theme_slugs

        if in_collections and in_themes:
            raise ValueError(
                f"Post pk={post.pk}: category '{category.name}' (slug={category.slug}) "
                "matches both a Collection and a Theme.",
            )
        if not in_collections and not in_themes:
            raise ValueError(
                f"Post pk={post.pk}: category '{category.name}' (slug={category.slug}) "
                "matches neither a Collection nor a Theme.",
            )

        if in_collections:
            collection = Collection.objects.get(slug=category.slug, locale=category.locale)
            # Use `id`, not `pk`: modelcluster's in-memory queryset after .add() has no `pk` field.
            if post.collections.filter(id=collection.pk).exists():
                report.log(
                    f"  Post pk={post.pk}: collection '{category.name}' (slug={category.slug}) "
                    "already assigned.",
                )
                continue
            report.log(
                f"  Post pk={post.pk}: add collection '{category.name}' (slug={category.slug}).",
            )
            if not dry_run:
                post.collections.add(collection)
                changed = True
            continue

        theme = Theme.objects.get(slug=category.slug, locale=category.locale)
        if post.themes.filter(id=theme.pk).exists():
            report.log(
                f"  Post pk={post.pk}: theme '{category.name}' (slug={category.slug}) already assigned.",
            )
            continue
        report.log(f"  Post pk={post.pk}: add theme '{category.name}' (slug={category.slug}).")
        if not dry_run:
            post.themes.add(theme)
            changed = True

    # ParentalManyToManyField only persists through tables when the page is saved.
    if changed:
        post.save()


def run_phase(
    phase: int,
    config: MigrationConfig | None = None,
    *,
    dry_run: bool = False,
    log_file: TextIO | None = None,
    log_stdout: LogWriter | None = None,
) -> MigrationReport:
    """Run one migration phase (1–3); non-dry-run work is wrapped in ``transaction.atomic()``."""
    config = config or MigrationConfig()
    runners: dict[int, Callable[..., MigrationReport]] = {
        1: migrate_pages,
        2: create_taxonomies,
        3: assign_taxonomies,
    }
    try:
        runner = runners[phase]
    except KeyError as exc:
        raise ValueError(f"Unknown phase {phase!r}; expected 1, 2, or 3.") from exc
    if dry_run:
        return runner(config, dry_run=True, log_file=log_file, log_stdout=log_stdout)
    with transaction.atomic():
        return runner(config, dry_run=False, log_file=log_file, log_stdout=log_stdout)
