"""
Scope of each contributor on an instance with several sites.

These functions only compute the scope: they do not check whether the isolation is
enabled, so that each caller decides what to do when it is not
(see ``is_multisite_isolation_active``).
"""

from django.conf import settings
from django.core import checks
from django.db import DatabaseError
from django.db.models import Q, QuerySet
from wagtail.models import GroupPagePermission, Page, Site

SITES_FOR_USER_CACHE_ATTR = "_sf_multisite_sites"


def is_multisite_isolation_active() -> bool:
    """
    Whether each contributor is restricted to the sites of their groups.

    Only reads the SF_MULTISITE_ISOLATION_ENABLED setting, whatever the number of sites.
    """
    return bool(getattr(settings, "SF_MULTISITE_ISOLATION_ENABLED", False))


def get_sites_for_user(user) -> list[Site]:
    """
    Returns the sites a user has access to.

    A user has access to a site if a page permission of one of their groups is set on
    the root page of the site, one of its translations, one of their ancestors or one of
    their descendants. A superuser has access to every site, an inactive or anonymous
    user to none.

    The result is cached on the user object, for the duration of the request.
    """
    if not user.is_authenticated or not user.is_active:
        return []

    cached = getattr(user, SITES_FOR_USER_CACHE_ATTR, None)
    if cached is None:
        cached = _compute_sites_for_user(user)
        setattr(user, SITES_FOR_USER_CACHE_ATTR, cached)
    return list(cached)


def _compute_sites_for_user(user) -> list[Site]:
    sites = list(Site.objects.select_related("root_page").order_by("hostname", "port"))
    if user.is_superuser:
        return sites

    permission_paths = set(
        GroupPagePermission.objects.filter(group__in=user.groups.all()).values_list("page__path", flat=True)
    )
    if not permission_paths:
        return []

    # The translations of a root page are not below it in the tree
    translation_keys = {site.root_page.translation_key for site in sites}
    root_paths = {}
    for translation_key, path in Page.objects.filter(translation_key__in=translation_keys).values_list(
        "translation_key", "path"
    ):
        root_paths.setdefault(translation_key, set()).add(path)

    def is_accessible(site: Site) -> bool:
        return any(
            # The permission is set on a root page or one of its ancestors, or on one of its descendants
            root_path.startswith(permission_path) or permission_path.startswith(root_path)
            for root_path in root_paths.get(site.root_page.translation_key, {site.root_page.path})
            for permission_path in permission_paths
        )

    return [site for site in sites if is_accessible(site)]


def get_site_for_page(page: Page | None, parent_page: Page | None = None) -> Site | None:
    """
    Returns the site of a page, or None if the page is outside of every site.

    For a saved page, relies on ``Page.get_site()`` from Wagtail, which handles the
    translated root pages and, for nested sites, returns the most specific one.
    A page being created has no path yet: its site is the one of its parent page.
    """
    if page is not None and page.pk:
        return page.get_site()
    if parent_page is not None:
        return parent_page.get_site()
    return None


def get_objects_for_page_form(queryset: QuerySet, site: Site | None, current_values=()) -> QuerySet:
    """
    Returns the objects offered in the form of a page, among the given queryset, whose
    model has a ``site`` field.

    These are the objects of the site, or the objects without site if ``site`` is None.
    The values already selected on the page are kept, so that saving the page does not
    remove them. ``current_values`` accepts objects or primary keys.
    """
    in_scope = Q(site__isnull=True) if site is None else Q(site=site)
    current_pks = [getattr(value, "pk", value) for value in current_values or ()]
    if current_pks:
        in_scope |= Q(pk__in=current_pks)
    return queryset.filter(in_scope)


def check_multisite_isolation_setting(app_configs=None, databases=None, **kwargs) -> list:
    """
    Informs that the instance has several sites while the isolation is disabled.
    Only a piece of information: an instance may have several sites without isolation.

    Registered with the database tag: Django runs it with ``migrate`` and
    ``check --database default``, not with every command.
    """
    if not databases or is_multisite_isolation_active():
        return []

    try:
        has_several_sites = Site.objects.count() > 1
    except DatabaseError:
        # Before the first migration
        return []

    if not has_several_sites:
        return []

    return [
        checks.Info(
            "L’instance a plusieurs sites et le cloisonnement multisite est désactivé : "
            "les contributeurs ne sont pas limités aux sites de leurs groupes.",
            hint="Pour les y limiter, activez la variable d’environnement SF_MULTISITE_ISOLATION_ENABLED.",
            id="sites_conformes_core.I001",
        )
    ]
