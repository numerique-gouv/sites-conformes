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


def get_sites_for_user(user, permission: str | None = None) -> list[Site]:
    """
    Returns the sites a user has access to.

    A user has access to a site if a page permission of one of their groups is set on
    the root page of the site, one of its translations, one of their ancestors or one of
    their descendants. A superuser has access to every site, an inactive or anonymous
    user to none.

    With ``permission`` (``"app_label.codename"``, for instance
    ``"wagtailredirects.change_redirect"``), only the groups that have this permission
    count: the result is the sites where the user has it. A permission given to the
    user directly, outside of a group, is not linked to any site and gives none.

    The result is cached on the user object, for the duration of the request.
    """
    if not user.is_authenticated or not user.is_active:
        return []

    cache = getattr(user, SITES_FOR_USER_CACHE_ATTR, None)
    if cache is None:
        cache = {}
        setattr(user, SITES_FOR_USER_CACHE_ATTR, cache)
    if permission not in cache:
        cache[permission] = _compute_sites_for_user(user, permission)
    return list(cache[permission])


def _compute_sites_for_user(user, permission: str | None) -> list[Site]:
    sites = list(Site.objects.select_related("root_page").order_by("hostname", "port"))
    if user.is_superuser:
        return sites

    groups = user.groups.all()
    if permission is not None:
        app_label, codename = permission.split(".")
        groups = groups.filter(permissions__content_type__app_label=app_label, permissions__codename=codename)

    permission_paths = set(GroupPagePermission.objects.filter(group__in=groups).values_list("page__path", flat=True))
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

    The site is the closest one whose root page contains the page. Otherwise, for a page
    below a translation of a root page, it is the site of this root page.
    A page being created has no path yet: its site is the one of its parent page.
    """
    if page is not None and page.pk:
        return _get_site_for_saved_page(page)
    if parent_page is not None:
        return _get_site_for_saved_page(parent_page)
    return None


def _get_site_for_saved_page(page: Page) -> Site | None:
    # Not Page.get_site() first: Wagtail attributes a page to every site whose root page
    # or one of its translations contains it, so with a site for each language, it returns
    # the first site in the order of their URL paths, whatever the language of the page.
    sites = [site for site in Site.objects.select_related("root_page") if page.path.startswith(site.root_page.path)]
    if sites:
        return max(sites, key=lambda site: len(site.root_page.path))
    return page.get_site()


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
