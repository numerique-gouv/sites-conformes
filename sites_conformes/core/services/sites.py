"""
Creation of a site on an instance with several sites.

``create_site`` creates the home page, the ``Site``, the image collection, the groups of
the roles with their permissions, the translations of the home page, the menus, the
configuration and the workflow of a site. It is idempotent: called again with the same
hostname and port, it completes the site without duplicating anything, and it never
modifies the other sites.

The other functions are the steps of this creation, also used by the demo sites.
"""

import os
from dataclasses import dataclass, field
from io import StringIO

import swapper
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.db import transaction
from django.http.request import validate_host
from django.utils import translation
from django.utils.text import slugify
from django.utils.translation import gettext
from wagtail.coreutils import find_available_slug, get_content_languages
from wagtail.models import (
    Collection,
    GroupApprovalTask,
    GroupCollectionPermission,
    GroupPagePermission,
    GroupSitePermission,
    Locale,
    Page,
    Site,
    Workflow,
    WorkflowPage,
    WorkflowTask,
)

from sites_conformes.core.constants import (
    DEFAULT_ILLUSTRATIONS_COLLECTION,
    DEFAULT_ILLUSTRATIONS_DIR,
    DSFR_PICTOGRAMS_COLLECTION,
    DSFR_PICTOGRAMS_DIR,
    INSTALLED_IMAGE_COLLECTIONS,
)
from sites_conformes.core.models import CmsDsfrConfig
from sites_conformes.core.multisite_isolation import is_multisite_isolation_active
from sites_conformes.core.services.accessors import get_or_create_footer_bottom_menu, get_or_create_main_menu
from sites_conformes.menus.models import FooterBottomMenu, MainMenu

ContentPage = swapper.load_model("sites_conformes_core", "ContentPage")

ADMINISTRATORS = "Administrateurs"
MODERATORS = "Modérateurs"
EDITORS = "Éditeurs"

_MEDIA_PERMISSIONS = [
    "wagtailimages.add_image",
    "wagtailimages.change_image",
    "wagtailimages.choose_image",
    "wagtailimages.delete_image",
    "wagtaildocs.add_document",
    "wagtaildocs.change_document",
    "wagtaildocs.choose_document",
    "wagtaildocs.delete_document",
]

_SNIPPET_PERMISSIONS = [
    "wagtailadmin.access_admin",
    "sites_conformes_blog.add_category",
    "sites_conformes_blog.change_category",
    "sites_conformes_blog.delete_category",
    "sites_conformes_blog.add_organization",
    "sites_conformes_blog.change_organization",
    "sites_conformes_blog.delete_organization",
    "sites_conformes_blog.add_person",
    "sites_conformes_blog.change_person",
    "sites_conformes_blog.delete_person",
]

_MENU_PERMISSIONS = [
    "sites_conformes_menus.add_mainmenu",
    "sites_conformes_menus.change_mainmenu",
    "sites_conformes_menus.delete_mainmenu",
    "sites_conformes_menus.add_topmenu",
    "sites_conformes_menus.change_topmenu",
    "sites_conformes_menus.delete_topmenu",
    "sites_conformes_menus.add_footerbottommenu",
    "sites_conformes_menus.change_footerbottommenu",
    "sites_conformes_menus.delete_footerbottommenu",
]

# Permissions of each role. Page permissions are given on the home page of the site and
# its translations, collection permissions on the collection of the site, and site
# permissions on the site.
# The site administrators get no permission on the user accounts: a global permission
# would let them edit every account, the superadmins included.
ROLE_PERMISSIONS = {
    ADMINISTRATORS: {
        "page": ["add_page", "change_page", "publish_page", "bulk_delete_page", "lock_page", "unlock_page"],
        "collection": _MEDIA_PERMISSIONS,
        "model": _SNIPPET_PERMISSIONS
        + _MENU_PERMISSIONS
        + [
            "wagtailredirects.add_redirect",
            "wagtailredirects.change_redirect",
            "wagtailredirects.delete_redirect",
        ],
        # Site settings: a global permission would give access to the settings of every site
        "site": [
            "sites_conformes_core.change_cmsdsfrconfig",
            "sites_conformes_core.change_customscriptssettings",
        ],
    },
    MODERATORS: {
        "page": ["add_page", "change_page", "publish_page", "lock_page", "unlock_page"],
        "collection": _MEDIA_PERMISSIONS,
        "model": _SNIPPET_PERMISSIONS + _MENU_PERMISSIONS,
    },
    EDITORS: {
        "page": ["add_page", "change_page"],
        "collection": _MEDIA_PERMISSIONS,
        "model": _SNIPPET_PERMISSIONS,
    },
}


class SiteCreationError(Exception):
    pass


@dataclass
class SiteSetup:
    site: Site
    # False when the site already existed and has only been completed
    created: bool
    # The home page of the site, then its translations
    home_pages: list
    collection: Collection
    groups: dict
    workflow: Workflow
    warnings: list = field(default_factory=list)


def create_site(
    hostname: str,
    name: str,
    port: int | None = None,
    language_codes: list | None = None,
    with_starter_pages: bool = False,
    stdout=None,
) -> SiteSetup:
    """
    Creates a site, or completes it if a site already has this hostname and port.

    - `port`: defaults to the HOST_PORT setting, or 80.
    - `language_codes`: the languages of the site, the first one being the language of
      its home page. Defaults to the default language of the instance.
    - `with_starter_pages`: also creates the legal notice, accessibility and contact pages.
    - `stdout`: where the commands run by the creation write, discarded by default.

    The warnings for the operator are returned in `warnings`.
    """
    hostname = clean_hostname(hostname)
    name = (name or "").strip()
    if not name:
        raise SiteCreationError("Le nom du site est obligatoire.")
    port = port or get_default_port()
    stdout = stdout or StringIO()

    with transaction.atomic():
        locales = get_locales(language_codes)
        warnings = import_installed_images(stdout)

        site = Site.objects.filter(hostname=hostname, port=port).first()
        created = site is None
        if created:
            home = create_home_page(hostname, name, locales[0])
            site = Site.objects.create(hostname=hostname, port=port, site_name=name, root_page=home)
        elif site.site_name != name:
            warnings.append(
                f"Le site {hostname}:{port} existe déjà sous le nom « {site.site_name} » : "
                "ce nom est conservé, et le nom demandé est ignoré."
            )
            name = site.site_name

        home_pages = get_or_create_home_translations(site, locales)
        collection = get_or_create_site_collection(name)
        groups = get_or_create_site_groups(site, collection, name)
        workflow, workflow_warnings = get_or_create_site_workflow(site, groups, name)
        warnings += workflow_warnings
        get_or_create_site_menus(site, home_pages)
        get_or_create_site_config(site, name, several_languages=len(home_pages) > 1)

        if with_starter_pages:
            call_command("create_starter_pages", site=site.pk, stdout=stdout)

    warnings += get_site_warnings(hostname)

    return SiteSetup(
        site=site,
        created=created,
        home_pages=home_pages,
        collection=collection,
        groups=groups,
        workflow=workflow,
        warnings=warnings,
    )


# Parameters


def clean_hostname(hostname: str) -> str:
    hostname = (hostname or "").strip().lower()
    if not hostname or any(character in hostname for character in ":/ "):
        raise SiteCreationError(
            "Le nom d’hôte ne doit contenir ni protocole, ni port, ni chemin : par exemple « site-c.example.org »."
        )
    return hostname


def get_default_port() -> int:
    return int(settings.HOST_PORT or 80)


def get_locales(language_codes: list | None = None) -> list:
    """
    Returns the locales of the given languages, in the same order, created if needed.
    Defaults to the default locale.
    """
    if not language_codes:
        return [Locale.get_default()]

    available = get_content_languages()
    unknown = [code for code in language_codes if code not in available]
    if unknown:
        raise SiteCreationError(
            f"Langues inconnues : {', '.join(unknown)}. Langues possibles : {', '.join(available)}."
        )

    return [Locale.objects.get_or_create(language_code=code)[0] for code in dict.fromkeys(language_codes)]


# Pages


def create_home_page(hostname: str, name: str, locale: Locale) -> Page:
    """
    Creates the home page of a new site, right under the root of the tree, next to the
    home pages of the other sites. Its slug is derived from the hostname.
    """
    root = Page.get_first_root_node()
    slug = find_available_slug(root, slugify(hostname.replace(".", "-")))
    home = root.add_child(instance=ContentPage(title=name, slug=slug, locale=locale, show_in_menus=False))
    home.save_revision().publish()
    return home


def get_site_root_pages(site: Site) -> list:
    """
    Returns the home page of the site and its translations: they are next to the home
    page in the tree, not below it.
    """
    home = site.root_page
    return [home] + list(home.get_translations().order_by("path"))


def get_or_create_home_translations(site: Site, locales: list) -> list:
    """
    Translates the home page of the site in the given locales if needed, and returns the
    home page and all its translations.
    """
    home = site.root_page.specific
    for locale in locales:
        if locale.pk != home.locale_id and home.get_translation_or_none(locale) is None:
            translated_home = home.copy_for_translation(locale)
            translated_home.save_revision().publish()

    return get_site_root_pages(site)


# Images


def get_or_create_site_collection(name: str) -> Collection:
    root_collection = Collection.get_first_root_node()
    return root_collection.get_children().filter(name=name).first() or root_collection.add_child(name=name)


def import_installed_images(stdout=None) -> list:
    """
    Imports the DSFR pictograms and the default illustrations, only if their collections
    don't exist yet: these images are shared by all the sites, so a new site must not
    duplicate nor replace them.

    Returns the warnings, when the static files to import are missing.
    """
    warnings = []
    imports = [
        (DSFR_PICTOGRAMS_COLLECTION, DSFR_PICTOGRAMS_DIR, "import_dsfr_pictograms"),
        (DEFAULT_ILLUSTRATIONS_COLLECTION, DEFAULT_ILLUSTRATIONS_DIR, "import_illustration_images"),
    ]
    for collection_name, directory, command in imports:
        if Collection.objects.filter(depth=2, name=collection_name).exists():
            continue
        if not os.path.isdir(directory):
            warnings.append(
                f"La collection « {collection_name} » n’existe pas, et ses images ne peuvent pas être importées "
                f"sans les fichiers statiques : lancez « collectstatic » puis « {command} »."
            )
            continue
        call_command(command, verbosity=0, stdout=stdout or StringIO())
    return warnings


# Groups and workflow


def get_permission(identifier: str) -> Permission:
    app_label, codename = identifier.split(".")
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


def get_site_group_name(site_name: str, role: str) -> str:
    return f"{site_name} – {role}"


def get_or_create_site_groups(site: Site, collection: Collection, name: str) -> dict:
    """
    Creates the groups of the roles of the site, and gives them their permissions.

    Existing groups only receive the missing permissions: the permissions added by a
    superadmin are kept.
    """
    root_pages = get_site_root_pages(site)
    groups = {}

    for role, permissions in ROLE_PERMISSIONS.items():
        group, _created = Group.objects.get_or_create(name=get_site_group_name(name, role))
        group.permissions.add(*[get_permission(identifier) for identifier in permissions["model"]])

        for codename in permissions["page"]:
            permission = get_permission(f"wagtailcore.{codename}")
            for root_page in root_pages:
                GroupPagePermission.objects.get_or_create(group=group, page=root_page, permission=permission)

        for identifier in permissions["collection"]:
            GroupCollectionPermission.objects.get_or_create(
                group=group, collection=collection, permission=get_permission(identifier)
            )

        for identifier in permissions.get("site", []):
            GroupSitePermission.objects.get_or_create(group=group, site=site, permission=get_permission(identifier))

        groups[role] = group

    grant_installed_images(groups.values())
    return groups


def grant_installed_images(groups) -> None:
    """
    Lets the groups choose the images imported at installation, without modifying or
    deleting them: only a superadmin can.
    """
    choose_image = get_permission("wagtailimages.choose_image")
    for collection in Collection.objects.filter(depth=2, name__in=INSTALLED_IMAGE_COLLECTIONS):
        for group in groups:
            GroupCollectionPermission.objects.get_or_create(
                group=group, collection=collection, permission=choose_image
            )


def get_or_create_site_workflow(site: Site, groups: dict, name: str) -> tuple:
    """
    Creates the workflow of the site, approved by its moderators and administrators,
    and assigns it to the home page of the site and its translations.

    A page that already follows another workflow keeps it. Returns the workflow and the
    warnings about these pages.
    """
    workflow = Workflow.objects.filter(name=f"Validation {name}").first() or Workflow.objects.create(
        name=f"Validation {name}"
    )
    task = GroupApprovalTask.objects.filter(name=f"Approbation {name}").first() or GroupApprovalTask.objects.create(
        name=f"Approbation {name}"
    )
    task.groups.add(groups[MODERATORS], groups[ADMINISTRATORS])
    WorkflowTask.objects.get_or_create(workflow=workflow, task=task, defaults={"sort_order": 0})

    warnings = []
    for root_page in get_site_root_pages(site):
        workflow_page, _created = WorkflowPage.objects.get_or_create(page=root_page, defaults={"workflow": workflow})
        if workflow_page.workflow_id != workflow.pk:
            warnings.append(
                f"La page « {root_page.title} » ({root_page.locale.language_code}) suit déjà le workflow "
                f"« {workflow_page.workflow.name} » : il n’est pas remplacé."
            )

    return workflow, warnings


# Menus and configuration


def get_or_create_site_menus(site: Site, home_pages: list) -> None:
    """
    Creates the main menu and the footer menu of the site in each language, if they
    don't exist yet. A new main menu only links to the home page.
    """
    main_menu = get_or_create_main_menu(site)
    footer_menu = get_or_create_footer_bottom_menu(site)

    for home_page in home_pages:
        locale = home_page.locale
        if locale.pk == main_menu.locale_id:
            continue

        if not MainMenu.objects.filter(site=site, locale=locale).exists():
            with translation.override(locale.language_code):
                link_text = gettext("Home page")
            MainMenu.objects.create(
                site=site,
                locale=locale,
                translation_key=main_menu.translation_key,
                items=[("link", {"text": link_text, "page": home_page, "link_type": "page"})],
            )

        if not FooterBottomMenu.objects.filter(site=site, locale=locale).exists():
            FooterBottomMenu.objects.create(site=site, locale=locale, translation_key=footer_menu.translation_key)


def get_or_create_site_config(site: Site, name: str, several_languages: bool) -> CmsDsfrConfig:
    """
    Creates the configuration of the site, with the language selector when the site
    has several languages. An existing configuration is not modified.
    """
    config, _created = CmsDsfrConfig.objects.get_or_create(
        site=site,
        defaults={"site_title": name, "language_selector_mode": "simple" if several_languages else "disabled"},
    )
    return config


# Warnings


def get_site_warnings(hostname: str) -> list:
    warnings = []

    if not validate_host(hostname, settings.ALLOWED_HOSTS):
        warnings.append(
            f"« {hostname} » n’est pas dans ALLOWED_HOSTS : le site ne répondra qu’une fois ce nom ajouté "
            "à cette variable d’environnement. La commande ne gère ni cette variable, ni le DNS, ni le certificat."
        )

    if not is_multisite_isolation_active():
        warnings.append(
            "Le cloisonnement multisite est désactivé (SF_MULTISITE_ISOLATION_ENABLED) : "
            "les contributeurs ne sont pas limités aux sites de leurs groupes."
        )
        groups_without_page_permission = list(
            Group.objects.filter(page_permissions__isnull=True).order_by("name").values_list("name", flat=True)
        )
        if groups_without_page_permission:
            warnings.append(
                "Groupes sans droit de page, qui n’auront accès à aucun contenu cloisonné une fois le "
                f"cloisonnement activé : {', '.join(groups_without_page_permission)}."
            )

    return warnings
