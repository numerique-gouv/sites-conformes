"""
Scope of each contributor on an instance with several sites.

The functions only compute the scope: they do not check whether the isolation is
enabled, so that each caller decides what to do when it is not
(see ``is_multisite_isolation_active``).

``SiteScopedViewSetMixin`` applies the scope to the admin views of a model with a
``site`` field, and only does so when the isolation is enabled.
``SuperuserOnlyViewSetMixin`` reserves the admin views of a model shared by every site
to the superusers, also only when the isolation is enabled.
"""

from dataclasses import dataclass
from functools import reduce, wraps
from operator import or_

from django.conf import settings
from django.contrib.admin.utils import unquote
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core import checks
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.db.models import Model, Q, QuerySet
from django.http import Http404
from wagtail.models import GroupPagePermission, Page, Site
from wagtail.permission_policies.base import ModelPermissionPolicy

SITES_FOR_USER_CACHE_ATTR = "_sf_multisite_sites"
MIDDLEWARE_PATH = "sites_conformes.core.middleware.MultisiteIsolationMiddleware"

# Models whose admin views use SiteScopedViewSetMixin, with the viewset that registered them
SITE_SCOPED_VIEWSETS = {}
# Same for SuperuserOnlyViewSetMixin
SUPERUSER_ONLY_VIEWSETS = {}


def is_multisite_isolation_active() -> bool:
    """
    Whether each contributor is restricted to the sites of their groups.

    Only reads the SF_MULTISITE_ISOLATION_ENABLED setting, whatever the number of sites.
    """
    # Not defined in the settings of the projects that use the package
    return getattr(settings, "SF_MULTISITE_ISOLATION_ENABLED", False)


def get_sites_for_user(user, permission: str | None = None) -> list[Site]:
    """
    Returns the sites a user has access to.

    A user has access to a site if a page permission of one of their groups is set on
    the root page of the site, one of its translations, one of their ancestors or one of
    their descendants. A superuser has access to every site, an inactive or anonymous
    user to none.

    With nested sites, a permission on a page of the inner site also gives access to the
    outer one, as the page is below its root page.

    With ``permission`` (``"app_label.codename"``, for instance
    ``"wagtailredirects.change_redirect"``), only the groups that have this permission
    count: the result is the sites where the user has it. A permission given to the
    user directly, outside of a group, is not linked to any site and gives none.
    Raises ValueError if the permission is badly formatted or does not exist.

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
    """
    Computes the result of ``get_sites_for_user``, without the cache.
    """
    # Checked before the superuser shortcut, so that a typo is noticed with every account
    permission_filter = None if permission is None else _get_permission_filter(permission)

    sites = list(Site.objects.select_related("root_page").order_by("hostname", "port"))
    if user.is_superuser:
        return sites

    groups = user.groups.all()
    if permission_filter is not None:
        groups = groups.filter(permission_filter)

    permission_paths = set(GroupPagePermission.objects.filter(group__in=groups).values_list("page__path", flat=True))
    if not permission_paths:
        return []

    root_paths = _get_site_root_paths(sites)

    def is_accessible(site: Site) -> bool:
        """
        Whether a page permission of the groups covers the site.
        """
        return any(
            # The permission is set on a root page or one of its ancestors, or on one of its descendants
            root_path.startswith(permission_path) or permission_path.startswith(root_path)
            for root_path in root_paths[site.pk]
            for permission_path in permission_paths
        )

    return [site for site in sites if is_accessible(site)]


def _get_site_root_paths(sites: list[Site]) -> dict[int, set[str]]:
    """
    Returns the paths of the root page of each site and of its translations, by site primary key.
    """
    # The translations of a root page are not below it in the tree
    translation_keys = {site.root_page.translation_key for site in sites}
    paths_by_key = {}
    for translation_key, path in Page.objects.filter(translation_key__in=translation_keys).values_list(
        "translation_key", "path"
    ):
        paths_by_key.setdefault(translation_key, set()).add(path)
    return {site.pk: paths_by_key.get(site.root_page.translation_key, {site.root_page.path}) for site in sites}


def _get_permission_filter(permission: str) -> Q:
    """
    Returns a filter on the groups that have the permission, after checking that it exists.
    """
    app_label, _, codename = permission.partition(".")
    if not app_label or not codename:
        raise ValueError(f'Expected a permission formatted as "app_label.codename", got "{permission}".')
    permission_filter = Q(permissions__content_type__app_label=app_label, permissions__codename=codename)
    if not Permission.objects.filter(content_type__app_label=app_label, codename=codename).exists():
        raise ValueError(f'Unknown permission "{permission}".')
    return permission_filter


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
    """
    Returns the site of a page that has a path, see ``get_site_for_page``.
    """
    # Not Page.get_site() first: Wagtail attributes a page to every site whose root page
    # or one of its translations contains it, so with a site for each language, it returns
    # the first site in the order of their URL paths, whatever the language of the page.
    sites = [site for site in Site.objects.select_related("root_page") if page.path.startswith(site.root_page.path)]
    if sites:
        return max(sites, key=lambda site: len(site.root_page.path))
    return page.get_site()


def get_objects_for_page_form(queryset: QuerySet, site: Site | None, current_values=()) -> QuerySet:
    """
    Returns the choices of a field of a page form, among the given queryset, whose model
    has a ``site`` field: for instance the categories offered in the form of a blog entry,
    with ``site`` given by ``get_site_for_page``.

    These are the objects of the site, or the objects without site if ``site`` is None.
    The values already selected on the page are kept, even from another site (for
    instance after the page was moved from another site): otherwise the form would reject
    them, or saving the page would remove them. ``current_values`` accepts objects or
    primary keys.
    """
    in_scope = Q(site__isnull=True) if site is None else Q(site=site)
    current_pks = [getattr(value, "pk", value) for value in current_values or ()]
    if current_pks:
        in_scope |= Q(pk__in=current_pks)
    return queryset.filter(in_scope)


@dataclass(frozen=True)
class _PageScope:
    # Paths of the root pages of the sites in the scope, and of their translations
    root_paths: frozenset
    # Paths of the root pages of the other sites, nested below the previous ones
    excluded_root_paths: frozenset
    # Paths of the ancestors of the root pages of the scope, to browse the tree down to them
    ancestor_paths: frozenset


def _get_page_scope(sites: list[Site]) -> _PageScope:
    """
    Computes the paths that delimit the pages of the given sites, see ``get_pages_in_scope_filter``.
    """
    all_sites = list(Site.objects.select_related("root_page"))
    root_paths_by_site = _get_site_root_paths(all_sites)
    site_pks = {site.pk for site in sites}

    root_paths = {path for pk in site_pks for path in root_paths_by_site.get(pk, ())}
    excluded_root_paths = {
        path
        for pk, paths in root_paths_by_site.items()
        if pk not in site_pks
        for path in paths
        if path not in root_paths and any(path.startswith(root_path) for root_path in root_paths)
    }
    ancestor_paths = {
        root_path[: depth * Page.steplen]
        for root_path in root_paths
        for depth in range(1, len(root_path) // Page.steplen)
    }
    return _PageScope(frozenset(root_paths), frozenset(excluded_root_paths), frozenset(ancestor_paths))


def get_pages_in_scope_filter(sites: list[Site]) -> Q:
    """
    Returns a filter on the pages of the given sites, for instance the sites of
    ``get_sites_for_user``.

    These are the pages below the root page of each site or one of its translations,
    except the pages of another site nested below it, as ``get_site_for_page`` gives them
    to the nested site. The ancestors of these root pages (at least the root of the tree)
    are also kept, so that the tree can be browsed down to the sites.
    """
    scope = _get_page_scope(sites)
    if not scope.root_paths:
        return Q(pk__in=[])

    in_sites = reduce(or_, (Q(path__startswith=path) for path in sorted(scope.root_paths)))
    for path in sorted(scope.excluded_root_paths):
        in_sites &= ~Q(path__startswith=path)
    return in_sites | Q(path__in=sorted(scope.ancestor_paths))


def is_page_in_scope(page: Page, sites: list[Site]) -> bool:
    """
    Whether the page is kept by ``get_pages_in_scope_filter`` for the given sites.
    """
    scope = _get_page_scope(sites)
    if page.path in scope.ancestor_paths:
        return True
    return any(page.path.startswith(path) for path in scope.root_paths) and not any(
        page.path.startswith(path) for path in scope.excluded_root_paths
    )


def get_sites_for_model_permissions(user, model: type[Model], actions) -> list[Site]:
    """
    Returns the sites where the user has at least one of the permissions on the model
    given by ``actions`` (for instance ``["change", "delete"]``), see ``get_sites_for_user``.

    The actions without a permission for this model are ignored: for instance
    ``"publish"`` for a model without draft state.
    """
    content_type = ContentType.objects.get_for_model(model, for_concrete_model=False)
    codenames = [f"{action}_{model._meta.model_name}" for action in actions]
    existing_codenames = set(
        Permission.objects.filter(content_type=content_type, codename__in=codenames).values_list("codename", flat=True)
    )

    sites = {}
    for codename in codenames:
        if codename in existing_codenames:
            for site in get_sites_for_user(user, f"{content_type.app_label}.{codename}"):
                sites.setdefault(site.pk, site)
    return sorted(sites.values(), key=lambda site: (site.hostname, site.port))


def get_groups_without_site(models) -> dict[Group, list[type[Model]]]:
    """
    Returns the groups that have a permission on one of the given models but no page
    permission: with the isolation enabled, they give access to no site, so their members
    lose access to these models. Each group comes with the models it has a permission on.
    """
    content_types = ContentType.objects.get_for_models(*models, for_concrete_models=False)
    models_by_content_type = {content_type.pk: model for model, content_type in content_types.items()}

    groups = {}
    for group in (
        Group.objects.filter(permissions__content_type__in=models_by_content_type.keys())
        .exclude(pk__in=GroupPagePermission.objects.values("group"))
        .distinct()
        .order_by("name")
    ):
        group_content_types = set(
            group.permissions.filter(content_type__in=models_by_content_type.keys()).values_list(
                "content_type", flat=True
            )
        )
        groups[group] = sorted(
            (models_by_content_type[pk] for pk in group_content_types), key=lambda model: model._meta.label
        )
    return groups


def get_user_scope_sites(user, model: type[Model], actions) -> list[Site] | None:
    """
    Returns the sites the user is restricted to for the given actions on a site-scoped
    model, or None when the user is not restricted: isolation disabled, or superuser.
    """
    if not is_multisite_isolation_active() or user.is_superuser:
        return None
    return get_sites_for_model_permissions(user, model, actions)


class SiteScopedFormMixin:
    """
    Restricts the site field of a ``WagtailAdminModelForm`` to the sites of the user
    (``for_user``) with the isolation enabled.

    For a new object, the site is the only site of the scope, if any: the default value
    of the model field (often the first site) does not apply.
    """

    site_field_name = "site"

    def __init__(self, *args, **kwargs):
        """
        Restricts the choices and the initial value of the site field to the scope of the user.
        """
        super().__init__(*args, **kwargs)
        field = self.fields.get(self.site_field_name)
        if self.for_user is None or field is None:
            return

        model = self._meta.model
        is_new = self.instance.pk is None
        sites = get_user_scope_sites(self.for_user, model, ["add" if is_new else "change"])
        if sites is None:
            return

        site_pks = [site.pk for site in sites]
        field.queryset = field.queryset.filter(pk__in=site_pks)
        if is_new and not self.is_bound:
            current_pk = self.initial.get(self.site_field_name)
            default_pk = model._meta.get_field(self.site_field_name).get_default()
            # Kept for a copy, unless it is also the default value
            if current_pk not in site_pks or current_pk == default_pk:
                self.initial[self.site_field_name] = site_pks[0] if len(site_pks) == 1 else None


class SiteScopedChooserViewMixin:
    """
    Restricts the objects of a chooser view to the scope of the user, see ``SiteScopedViewSetMixin``.
    """

    site_scoped_viewset = None

    def get_object_list(self):
        """
        Returns the objects offered by the chooser, in the scope only.
        """
        return self.site_scoped_viewset.filter_queryset(super().get_object_list(), self.request.user)

    def get_object(self, pk):
        """
        Returns the chosen object, which must be in the scope.
        """
        return self.site_scoped_viewset.filter_queryset(self.model_class.objects.all(), self.request.user).get(pk=pk)

    def get_objects(self, pks):
        """
        Returns the chosen objects (multiple choice), in the scope only.
        """
        return self.site_scoped_viewset.filter_queryset(super().get_objects(pks), self.request.user)


class SiteScopedViewSetMixin:
    """
    Restricts the admin views of a ``ModelViewSet`` (or ``SnippetViewSet``) to the sites
    of the user, for a model with a foreign key to ``Site`` (``site_field_name``).

    With the isolation disabled, or for a superuser, it changes nothing. Otherwise:

    - the listing and the chooser only show the objects of the user's sites;
    - the site field of the form only offers these sites (see ``SiteScopedFormMixin``);
    - every view of an object outside of the scope returns a 404: edit, delete, copy,
      history, usage, revisions, previews, etc.

    The sites of the scope depend on the permission required by each view: an object is
    editable on the sites where the user has the ``change`` permission on the model. The
    listing shows the sites of any of the ``scope_actions``.

    The views outside of the viewset (bulk actions, wagtail-localize) are restricted by
    ``sites_conformes.core.middleware.MultisiteIsolationMiddleware``.
    """

    site_field_name = "site"
    scope_actions = ("add", "change", "delete", "view")

    def on_register(self):
        """
        Records the model as site-scoped, for the middleware and the system checks.
        """
        super().on_register()
        SITE_SCOPED_VIEWSETS[self.model] = self

    def get_scope_sites(self, user, actions=None) -> list[Site] | None:
        """
        Returns the sites the user is restricted to, or None if they are not restricted.
        """
        return get_user_scope_sites(user, self.model, actions or self.scope_actions)

    def filter_queryset(self, queryset: QuerySet, user, actions=None) -> QuerySet:
        """
        Keeps the objects of the queryset that are in the scope of the user for the given actions.
        """
        sites = self.get_scope_sites(user, actions)
        if sites is None:
            return queryset
        return queryset.filter(**{f"{self.site_field_name}__in": sites})

    def is_in_scope(self, user, pk, actions=None) -> bool:
        """
        Whether the object with this primary key is in the scope of the user for the given actions.
        """
        return self.filter_queryset(self.model._default_manager.filter(pk=pk), user, actions).exists()

    def get_queryset(self, request):
        """
        Returns the objects of the listing, in the scope only.
        """
        queryset = super().get_queryset(request)
        if self.get_scope_sites(request.user) is None:
            return queryset
        if queryset is None:
            queryset = self.model._default_manager.all()
        return self.filter_queryset(queryset, request.user)

    def get_form_class(self, for_update=False):
        """
        Returns the form class of the create and edit views, with the site field restricted.
        """
        form_class = super().get_form_class(for_update)
        if issubclass(form_class, SiteScopedFormMixin):
            return form_class
        return type(
            f"SiteScoped{form_class.__name__}",
            (SiteScopedFormMixin, form_class),
            {"site_field_name": self.site_field_name},
        )

    @staticmethod
    def get_view_actions(view_class) -> list[str] | None:
        """
        Returns the actions whose sites give access to a view, from its permissions.
        """
        if permission := getattr(view_class, "permission_required", None):
            return [permission]
        if permissions := getattr(view_class, "any_permission_required", None):
            return list(permissions)
        return None

    def construct_view(self, view_class, **kwargs):
        """
        Wraps each view so that an object outside of the scope returns a 404.
        """
        view = super().construct_view(view_class, **kwargs)
        actions = self.get_view_actions(view_class)

        @wraps(view)
        def site_scoped_view(request, *args, **view_kwargs):
            """
            Checks the scope before calling the view.
            """
            if "pk" in view_kwargs:
                if not self.is_in_scope(request.user, unquote(str(view_kwargs["pk"])), actions):
                    raise Http404
            elif actions == ["add"] and self.get_scope_sites(request.user, actions) == []:
                raise PermissionDenied
            return view(request, *args, **view_kwargs)

        return site_scoped_view

    @property
    def chooser_viewset(self):
        """
        Returns the chooser viewset of the model, with its views restricted to the scope.
        """
        viewset = super().chooser_viewset
        for attr in [
            "choose_view_class",
            "choose_results_view_class",
            "chosen_view_class",
            "chosen_multiple_view_class",
        ]:
            view_class = getattr(viewset, attr)
            setattr(
                viewset,
                attr,
                type(
                    f"SiteScoped{view_class.__name__}",
                    (SiteScopedChooserViewMixin, view_class),
                    {"site_scoped_viewset": self},
                ),
            )
        return viewset


class SuperuserOnlyPermissionPolicy(ModelPermissionPolicy):
    """
    Model permissions, that only superusers have when the isolation is enabled, whatever
    the permissions of the groups (see ``SuperuserOnlyViewSetMixin``).
    """

    def user_has_permission(self, user, action):
        if is_multisite_isolation_active() and not user.is_superuser:
            return False
        return super().user_has_permission(user, action)

    def users_with_any_permission(self, actions):
        users = super().users_with_any_permission(actions)
        if is_multisite_isolation_active():
            users = users.filter(is_superuser=True)
        return users


class SuperuserOnlyViewSetMixin:
    """
    Reserves the admin views of a ``SnippetViewSet`` to the superusers, for a model shared
    by every site, such as the tags.

    With the isolation disabled, it changes nothing. Otherwise, for the other users, the
    model disappears from the menu and the listing of the snippets, whatever the
    permissions of their groups, and its views, the bulk actions included, deny the
    access as the Wagtail admin does (see ``is_superuser_only_view``). The chooser stays
    open: choosing an object, for instance a tag in the filter of a block, is not
    managing it.
    """

    def on_register(self):
        """
        Records the model as reserved to the superusers, for the middleware.
        """
        super().on_register()
        SUPERUSER_ONLY_VIEWSETS[self.model] = self

    @property
    def permission_policy(self):
        return SuperuserOnlyPermissionPolicy(self.model)


def is_superuser_only_view(resolver_match, view_kwargs) -> bool:
    """
    Whether the resolved admin view belongs to a viewset using ``SuperuserOnlyViewSetMixin``,
    or is a bulk action on its model. The chooser of the viewset is not one of them.

    Checked by ``MultisiteIsolationMiddleware``, for all these views at once.
    """
    for model, viewset in SUPERUSER_ONLY_VIEWSETS.items():
        if resolver_match.namespace == viewset.url_namespace:
            return True
        if resolver_match.view_name == "wagtail_bulk_action" and (
            view_kwargs.get("app_label"),
            view_kwargs.get("model_name"),
        ) == (model._meta.app_label, model._meta.model_name):
            return True
    return False


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
            "The instance has several sites and the multisite isolation is disabled: "
            "contributors are not restricted to the sites of their groups.",
            hint="To restrict them, enable the SF_MULTISITE_ISOLATION_ENABLED environment variable.",
            id="sites_conformes_core.I001",
        )
    ]


def get_site_scoped_models() -> list[type[Model]]:
    """
    Returns the models whose admin views use ``SiteScopedViewSetMixin``.
    """
    # The viewsets are registered in the wagtail_hooks modules, loaded on demand
    from wagtail.hooks import search_for_hooks

    search_for_hooks()
    return sorted(SITE_SCOPED_VIEWSETS, key=lambda model: model._meta.label)


def check_groups_without_site(app_configs=None, databases=None, **kwargs) -> list:
    """
    Warns about the groups that would give access to no site with the isolation
    enabled, see ``get_groups_without_site``. Only on an instance with several sites.

    Registered with the database tag, like ``check_multisite_isolation_setting``.
    """
    if not databases:
        return []

    try:
        if Site.objects.count() <= 1:
            return []
        groups = get_groups_without_site(get_site_scoped_models())
    except DatabaseError:
        # Before the first migration
        return []

    if not groups:
        return []

    names = ", ".join(f'"{group.name}"' for group in groups)
    return [
        checks.Warning(
            f"These groups have permissions on site-scoped models but no page permission: {names}. "
            "With the multisite isolation enabled, they give access to no site.",
            hint="Give them a page permission on their sites. Details: python manage.py multisite_isolation_report",
            id="sites_conformes_core.W001",
        )
    ]


def check_multisite_isolation_middleware(app_configs=None, **kwargs) -> list:
    """
    Warns that the isolation is enabled without its middleware, which restricts the
    pages and the views outside of the viewsets.
    """
    if not is_multisite_isolation_active() or MIDDLEWARE_PATH in settings.MIDDLEWARE:
        return []
    return [
        checks.Warning(
            "The multisite isolation is enabled but its middleware is missing: "
            "contributors can still browse the pages of every site.",
            hint=f'Add "{MIDDLEWARE_PATH}" to MIDDLEWARE, after the authentication middleware.',
            id="sites_conformes_core.W002",
        )
    ]
