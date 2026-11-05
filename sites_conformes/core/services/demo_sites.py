"""
Fictional demo sites used to develop and test the multisite features.

The contents are described in ``sites_conformes/core/demo_data/content.json``
and the images in ``sites_conformes/core/demo_data/img/``. Neither is shipped
with the package: this service only works from a checkout of the repository.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.db import transaction
from django.test import override_settings
from django.utils import timezone
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
from wagtail.rich_text import RichText

from sites_conformes.blog.models import BlogEntryPage, BlogIndexPage, Category, Organization, Person
from sites_conformes.core.models import CmsDsfrConfig, ContentPage
from sites_conformes.core.utils import get_closest_image_ratio, import_image
from sites_conformes.events.models import EventEntryPage, EventsIndexPage
from sites_conformes.forms.models import FormField, FormPage
from sites_conformes.menus.models import FooterBottomMenu, MainMenu

DEMO_DATA_DIR = Path(__file__).resolve().parent.parent / "demo_data"
DEMO_IMAGES_DIR = DEMO_DATA_DIR / "img"

# Password of the fictional demo accounts, for development only
DEFAULT_PASSWORD = "demo-sites-conformes"  # nosec B105

SITE_KEYS = ("a", "b")

ADMINISTRATORS = "Administrateurs"
MODERATORS = "Modérateurs"
EDITORS = "Éditeurs"

# Permissions of each role, following the roles table of the multisite plan.
# Page permissions are given on the home page of the site and its translations,
# collection and site permissions on the collection and the site.
ROLE_PERMISSIONS = {
    ADMINISTRATORS: {
        "page": ["add_page", "change_page", "publish_page", "bulk_delete_page", "lock_page", "unlock_page"],
        "collection": [
            "wagtailimages.add_image",
            "wagtailimages.change_image",
            "wagtailimages.choose_image",
            "wagtailimages.delete_image",
            "wagtaildocs.add_document",
            "wagtaildocs.change_document",
            "wagtaildocs.choose_document",
            "wagtaildocs.delete_document",
        ],
        "model": [
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
            "sites_conformes_menus.add_mainmenu",
            "sites_conformes_menus.change_mainmenu",
            "sites_conformes_menus.delete_mainmenu",
            "sites_conformes_menus.add_topmenu",
            "sites_conformes_menus.change_topmenu",
            "sites_conformes_menus.delete_topmenu",
            "sites_conformes_menus.add_footerbottommenu",
            "sites_conformes_menus.change_footerbottommenu",
            "sites_conformes_menus.delete_footerbottommenu",
            "wagtailredirects.add_redirect",
            "wagtailredirects.change_redirect",
            "wagtailredirects.delete_redirect",
            "auth.add_user",
            "auth.change_user",
            "auth.delete_user",
        ],
        # Site settings: a global permission would give access to the settings of every site
        "site": [
            "sites_conformes_core.change_cmsdsfrconfig",
            "sites_conformes_core.change_customscriptssettings",
        ],
    },
    MODERATORS: {
        "page": ["add_page", "change_page", "publish_page", "lock_page", "unlock_page"],
        "collection": [
            "wagtailimages.add_image",
            "wagtailimages.change_image",
            "wagtailimages.choose_image",
            "wagtailimages.delete_image",
            "wagtaildocs.add_document",
            "wagtaildocs.change_document",
            "wagtaildocs.choose_document",
            "wagtaildocs.delete_document",
        ],
        "model": [
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
            "sites_conformes_menus.add_mainmenu",
            "sites_conformes_menus.change_mainmenu",
            "sites_conformes_menus.delete_mainmenu",
            "sites_conformes_menus.add_topmenu",
            "sites_conformes_menus.change_topmenu",
            "sites_conformes_menus.delete_topmenu",
            "sites_conformes_menus.add_footerbottommenu",
            "sites_conformes_menus.change_footerbottommenu",
            "sites_conformes_menus.delete_footerbottommenu",
        ],
    },
    EDITORS: {
        "page": ["add_page", "change_page"],
        "collection": [
            "wagtailimages.add_image",
            "wagtailimages.change_image",
            "wagtailimages.choose_image",
            "wagtailimages.delete_image",
            "wagtaildocs.add_document",
            "wagtaildocs.change_document",
            "wagtaildocs.choose_document",
            "wagtaildocs.delete_document",
        ],
        "model": [
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
        ],
    },
}

# Collections created at installation, that every contributor can choose images from.
SHARED_COLLECTIONS = ["Pictogrammes DSFR", "Illustrations par défaut"]

# (username, first name, last name, {site key: [roles]})
DEMO_USERS = [
    ("admin-a", "Alice", "Administratrice A", {"a": [ADMINISTRATORS]}),
    ("moderateur-a", "Marc", "Modérateur A", {"a": [MODERATORS]}),
    ("editeur-a", "Emma", "Éditrice A", {"a": [EDITORS]}),
    ("admin-b", "Bruno", "Administrateur B", {"b": [ADMINISTRATORS]}),
    ("moderateur-b", "Margot", "Modératrice B", {"b": [MODERATORS]}),
    ("editeur-b", "Elias", "Éditeur B", {"b": [EDITORS]}),
    ("editeur-ab", "Eva", "Éditrice A et B", {"a": [EDITORS], "b": [EDITORS]}),
]


class DemoSitesError(Exception):
    pass


@dataclass
class DemoSites:
    sites: dict = field(default_factory=dict)
    groups: dict = field(default_factory=dict)
    users: dict = field(default_factory=dict)
    password: str = DEFAULT_PASSWORD


def load_demo_content() -> dict:
    with open(DEMO_DATA_DIR / "content.json", encoding="utf-8") as content_file:
        return json.load(content_file)


def get_permission(identifier: str) -> Permission:
    app_label, codename = identifier.split(".")
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


def get_site_group(site_key: str, role: str, content: dict | None = None) -> Group:
    content = content or load_demo_content()
    site_name = next(spec["site_name"] for spec in content["sites"] if spec["key"] == site_key)
    return Group.objects.get(name=f"{site_name} – {role}")


def create_demo_users(site_keys: list, password: str = DEFAULT_PASSWORD, only_cross_site: bool = False) -> dict:
    """
    Creates the superadmin and the accounts of the given sites, whose groups must exist.
    With only_cross_site, only creates the accounts that belong to several sites
    (used when loading the reference bases, which are split by site).
    """
    User = get_user_model()
    content = load_demo_content()
    # Hashing once keeps the creation fast, and the hashes identical between users
    hashed_password = make_password(password)
    users = {}

    if not only_cross_site:
        users["superadmin"] = User.objects.create(
            username="superadmin",
            email="superadmin@example.org",
            first_name="Sacha",
            last_name="Superadmin",
            is_staff=True,
            is_superuser=True,
            password=hashed_password,
        )

    for username, first_name, last_name, memberships in DEMO_USERS:
        if not set(memberships) <= set(site_keys) or (only_cross_site and len(memberships) < 2):
            continue

        user = User.objects.create(
            username=username,
            email=f"{username}@example.org",
            first_name=first_name,
            last_name=last_name,
            password=hashed_password,
        )
        for site_key, roles in memberships.items():
            user.groups.add(*[get_site_group(site_key, role, content) for role in roles])
        users[username] = user

    return users


def check_empty_database() -> None:
    """
    The demo sites replace the initial Wagtail page, so they are only created on a new database.
    """
    if Page.objects.filter(depth__gt=2).exists() or Page.objects.filter(depth=2).count() > 1:
        raise DemoSitesError(
            "La base contient déjà des pages : les sites de démo ne se créent que sur une base vide "
            "(par exemple après « just clear-local-db » puis « just migrate »)."
        )


def create_demo_sites(
    site_keys: tuple = SITE_KEYS, with_media: bool = True, password: str = DEFAULT_PASSWORD
) -> DemoSites:
    """
    Creates the fictional demo sites on an empty database: both sites by default,
    or a single one ("a" or "b") for a monosite instance.
    """
    check_empty_database()

    # Translations get their slug after being copied: this is not a move that needs a redirect.
    # The setting must still be overridden when the transaction is committed, as Wagtail
    # creates the redirects at that moment.
    with override_settings(WAGTAILREDIRECTS_AUTO_CREATE=False), transaction.atomic():
        builder = DemoSitesBuilder(load_demo_content(), site_keys=site_keys, with_media=with_media)
        return builder.build(password)


class DemoSitesBuilder:
    def __init__(self, content: dict, site_keys: tuple, with_media: bool):
        unknown = set(site_keys) - set(SITE_KEYS)
        if unknown or not site_keys:
            raise DemoSitesError(f"Sites inconnus : {sorted(unknown)}. Valeurs possibles : {', '.join(SITE_KEYS)}")
        self.content = content
        self.site_keys = list(site_keys)
        self.with_media = with_media

        self.locale_fr = Locale.get_default()
        self.locale_en, _created = Locale.objects.get_or_create(language_code="en")

        self.images = {}
        self.categories = {}
        self.organizations = {}
        self.persons = {}
        self.result = DemoSites()

    def build(self, password: str) -> DemoSites:
        initial_pages = list(Page.objects.filter(depth=2).values_list("pk", flat=True))
        site_specs = [spec for spec in self.content["sites"] if spec["key"] in self.site_keys]

        collections = {spec["key"]: self.create_collection(spec) for spec in site_specs}

        if self.with_media:
            self.import_shared_images()
            self.import_images(collections)

        self.create_categories()
        self.create_organizations_and_persons()

        for spec in site_specs:
            site = self.create_site(spec)
            self.result.sites[spec["key"]] = site
            groups = self.create_groups(spec, site, collections[spec["key"]])
            self.result.groups[spec["key"]] = groups
            self.create_workflow(spec, site, groups)

        # The "Welcome to Wagtail" page created at installation
        Page.objects.filter(pk__in=initial_pages).delete()
        self.create_users(password)
        self.result.password = password

        return self.result

    # Media

    def create_collection(self, spec: dict) -> Collection:
        return Collection.get_first_root_node().add_child(name=spec["site_name"])

    def import_shared_images(self) -> None:
        # These commands read the static files collected by "collectstatic"
        if os.path.isdir("staticfiles/dsfr/dist/artwork/pictograms/"):
            call_command("import_dsfr_pictograms", verbosity=0)
        if os.path.isdir("staticfiles/illustration/"):
            call_command("import_illustration_images", verbosity=0)

    def import_images(self, collections: dict) -> None:
        root_collection = Collection.get_first_root_node()

        for key, spec in self.content["images"].items():
            site_key = spec["site"]
            if site_key and site_key not in self.site_keys:
                continue

            image = import_image(str(DEMO_IMAGES_DIR / spec["file"]), spec["title"])
            image.description = spec["alt"]
            image.collection = collections[site_key] if site_key else root_collection
            image.save()
            self.images[key] = image

    def get_image(self, key: str | None):
        if not key:
            return None
        return self.images.get(key)

    # Snippets

    def create_categories(self) -> None:
        for spec in self.content["categories"]:
            parent = self.categories.get(spec.get("parent"))
            category = Category.objects.create(
                name=spec["name"],
                slug=spec["slug"],
                parent=parent,
                description=spec.get("description", ""),
                locale=self.locale_fr,
            )
            self.categories[spec["key"]] = category

            if "en" in spec:
                translation = category.copy_for_translation(self.locale_en)
                translation.name = spec["en"]["name"]
                translation.slug = spec["en"]["slug"]
                translation.parent = parent.get_translation(self.locale_en) if parent else None
                translation.save()

    def create_organizations_and_persons(self) -> None:
        for spec in self.content["organizations"]:
            self.organizations[spec["key"]] = Organization.objects.create(name=spec["name"], slug=spec["slug"])

        for spec in self.content["persons"]:
            self.persons[spec["key"]] = Person.objects.create(
                name=spec["name"],
                role=spec["role"],
                organization=self.organizations[spec["organization"]],
                contact_info=spec["contact_info"],
                image=self.get_image(spec["image"]),
            )

    # Pages

    def build_body(self, blocks: list) -> list:
        body = []
        for block in blocks:
            if "paragraph" in block:
                body.append(("paragraph", RichText(block["paragraph"])))
            elif "image" in block:
                image = self.get_image(block["image"])
                if image:
                    body.append(
                        (
                            "image",
                            {
                                "image": {"image": image, "alt_text": image.description, "decorative": False},
                                "width": block.get("width", ""),
                                "image_ratio": block.get("ratio") or get_closest_image_ratio(image),
                            },
                        )
                    )
            elif "imageandtext" in block:
                image = self.get_image(block["imageandtext"]["image"])
                text = RichText(block["imageandtext"]["text"])
                if image:
                    body.append(
                        (
                            "imageandtext",
                            {
                                "image": {"image": image, "alt_text": image.description, "decorative": False},
                                "image_side": "left",
                                "image_ratio": "4",
                                "text": text,
                            },
                        )
                    )
                else:
                    # Without media (in the tests), only the text is kept
                    body.append(("paragraph", text))
            elif "alert" in block:
                body.append(("alert", {**block["alert"], "heading_tag": "h2"}))
            elif "subpageslist" in block:
                body.append(("subpageslist", None))
            else:
                raise DemoSitesError(f"Bloc inconnu : {block}")
        return body

    def set_page_fields(self, page: Page, spec: dict) -> None:
        page.title = spec["title"]
        if "slug" in spec:
            page.slug = spec["slug"]
        if "body" in spec:
            page.body = self.build_body(spec["body"])
        if "intro" in spec:
            page.intro = RichText(spec["intro"])

    def build_hero(self, image_key: str | None) -> list:
        """
        Returns a header showing the page title over the darkened image, or no header.
        """
        image = self.get_image(image_key)
        if not image:
            return []
        return [
            (
                "old_hero",
                {
                    "header_with_title": True,
                    "header_image": {"image": image, "alt_text": "", "decorative": True},
                    "header_darken": True,
                },
            )
        ]

    def build_page(self, spec: dict) -> Page:
        page_type = spec.get("type", "content")

        if page_type == "contact":
            page = FormPage(
                thank_you_text=RichText("<p>Merci pour votre message ! Nous vous répondrons rapidement.</p>")
            )
        elif page_type == "blog_index":
            page = BlogIndexPage(filter_by_author=True, filter_by_source=True)
        elif page_type == "events_index":
            page = EventsIndexPage(filter_by_author=True, filter_by_source=True)
        else:
            page = ContentPage()

        self.set_page_fields(page, spec)
        page.show_in_menus = True

        page.hero = self.build_hero(spec.get("header_image"))
        return page

    def add_page(self, parent: Page, page: Page) -> Page:
        parent.add_child(instance=page)
        page.save_revision().publish()
        return page

    def create_tree(self, parent: Page, specs: list, footer_entries: list) -> list:
        """
        Creates the French pages, and returns (page, spec) pairs to translate.
        """
        created = []

        for spec in specs:
            page = self.add_page(parent, self.build_page(spec))
            created.append((page, spec))

            if spec.get("type") == "contact":
                self.create_form_fields(page)

            if spec.get("menu") == "footer":
                footer_entries.append((page, spec))

            for entry_spec in spec.get("entries", []):
                entry = self.add_page(page, self.build_entry(spec["type"], entry_spec))
                created.append((entry, entry_spec))

            created += self.create_tree(page, spec.get("children", []), footer_entries)

        return created

    def build_entry(self, index_type: str, spec: dict) -> Page:
        date = timezone.make_aware(datetime.fromisoformat(spec["date"]))
        categories = [self.categories[key] for key in spec.get("categories", [])]
        authors = [self.persons[key] for key in spec.get("authors", [])]

        if index_type == "events_index":
            entry = EventEntryPage(
                date=date,
                event_date_start=timezone.make_aware(datetime.fromisoformat(spec["start"])),
                event_date_end=timezone.make_aware(datetime.fromisoformat(spec["end"])),
                location=spec.get("location", ""),
            )
            entry.event_categories = categories
        else:
            entry = BlogEntryPage(date=date)
            entry.blog_categories = categories

        entry.authors = authors
        self.set_page_fields(entry, spec)
        entry.preview_image = self.get_image(spec.get("preview_image"))
        entry.hero = self.build_hero(spec.get("preview_image"))
        return entry

    def create_form_fields(self, page: FormPage) -> None:
        fields = [
            ("votre_nom_complet", "Votre nom complet", "singleline", "name"),
            ("votre_adresse_electronique", "Votre adresse électronique", "email", "email"),
            ("votre_message", "Votre message", "multiline", ""),
        ]
        for sort_order, (clean_name, label, field_type, autocomplete) in enumerate(fields):
            FormField.objects.create(
                page=page,
                sort_order=sort_order,
                clean_name=clean_name,
                label=label,
                field_type=field_type,
                autocomplete=autocomplete,
                required=True,
                locale=page.locale,
            )

    def translate_page(self, page: Page, spec_en: dict) -> Page:
        translation = page.copy_for_translation(self.locale_en)
        self.set_page_fields(translation, {"slug": page.slug, **spec_en})

        # Categories are translated, but persons are shared between languages
        if isinstance(translation, BlogEntryPage):
            translation.blog_categories = [
                category.get_translation_or_none(self.locale_en) or category for category in page.blog_categories.all()
            ]
            translation.authors = page.authors.all()

        translation.save_revision().publish()
        return translation

    # Sites

    def create_site(self, spec: dict) -> Site:
        root = Page.get_first_root_node()
        home_spec = spec["home"]
        home = self.add_page(root, self.build_page({"slug": f"accueil-{spec['key']}", **home_spec}))

        footer_entries = []
        to_translate = self.create_tree(home, home_spec.get("children", []), footer_entries)

        home_en = None
        if "en" in home_spec:
            # Both home pages are children of the root page, so they need different slugs
            home_en = self.translate_page(home, {"slug": f"{home.slug}-en", **home_spec["en"]})
        for page, page_spec in to_translate:
            if "en" in page_spec:
                self.translate_page(page, page_spec["en"])

        port = int(settings.HOST_PORT or 80)
        if not self.result.sites:
            # The first site replaces the site created by Wagtail at installation, and stays the default one
            site = Site.objects.get(is_default_site=True)
            site.hostname = spec["hostname"]
            site.port = port
            site.site_name = spec["site_name"]
            site.root_page = home
            site.save()
        else:
            site = Site.objects.create(
                hostname=spec["hostname"], port=port, site_name=spec["site_name"], root_page=home
            )

        CmsDsfrConfig.objects.update_or_create(site=site, defaults=spec["config"])
        self.create_menus(site, footer_entries, spec["main_menu"], with_english=home_en is not None)

        return site

    def get_menu_page(self, site: Site, path: str, locale: Locale) -> Page | None:
        """
        Gets a page of the site from its path of French slugs, in the given locale.
        """
        page = site.root_page
        for slug in path.split("/"):
            page = page.get_children().get(slug=slug)
        return page if locale == self.locale_fr else page.get_translation_or_none(locale)

    def build_main_menu_items(self, site: Site, menu_spec: list, locale: Locale) -> list:
        def link(path: str, text: str = "") -> dict | None:
            page = self.get_menu_page(site, path, locale)
            return {"text": text, "page": page, "link_type": "page"} if page else None

        result = []
        for item in menu_spec:
            if "link" in item:
                result.append(("link", link(item["link"])))
            elif "submenu" in item:
                submenu = item["submenu"]
                texts = submenu.get("en", {}) if locale != self.locale_fr else {}
                links = [("link", value) for value in map(link, submenu["links"]) if value]
                # Skipped when none of its pages is translated
                if links:
                    result.append(("submenu", {"label": texts.get("label", submenu["label"]), "links": links}))
            elif "megamenu" in item:
                megamenu = item["megamenu"]
                texts = megamenu.get("en", {}) if locale != self.locale_fr else {}
                columns = []
                for index, column in enumerate(megamenu["columns"]):
                    links = [("link", value) for value in map(link, column["links"]) if value]
                    label = texts["columns"][index] if texts else column["label"]
                    columns.append(("column", {"label": label, "links": links}))
                main_link = megamenu["main_link"]
                result.append(
                    (
                        "megamenu",
                        {
                            "label": texts.get("label", megamenu["label"]),
                            "description": texts.get("description", megamenu["description"]),
                            "main_link": link(main_link["page"], texts.get("main_link_text", main_link["text"])),
                            "columns": columns,
                        },
                    )
                )
        return [(block_type, value) for block_type, value in result if value]

    def create_menus(self, site: Site, footer_entries: list, main_menu_spec: list, with_english: bool) -> None:
        def footer_items(locale: Locale) -> list:
            result = []
            for page, spec in footer_entries:
                if locale != self.locale_fr:
                    page = page.get_translation_or_none(locale)
                    if not page:
                        continue
                    spec = spec.get("en", {})
                label = spec.get("footer_label") or page.title
                result.append(("link", {"text": label, "page": page, "link_type": "page"}))
            return result

        main_menu = MainMenu.objects.create(
            site=site, locale=self.locale_fr, items=self.build_main_menu_items(site, main_menu_spec, self.locale_fr)
        )
        footer_menu = FooterBottomMenu.objects.create(
            site=site, locale=self.locale_fr, items=footer_items(self.locale_fr)
        )

        if with_english:
            MainMenu.objects.create(
                site=site,
                locale=self.locale_en,
                translation_key=main_menu.translation_key,
                items=self.build_main_menu_items(site, main_menu_spec, self.locale_en),
            )
            FooterBottomMenu.objects.create(
                site=site,
                locale=self.locale_en,
                translation_key=footer_menu.translation_key,
                items=footer_items(self.locale_en),
            )

    # Groups, workflows and users

    def create_groups(self, spec: dict, site: Site, collection: Collection) -> dict:
        home = site.root_page
        roots = [home] + list(home.get_translations())
        shared_collections = Collection.objects.filter(name__in=SHARED_COLLECTIONS)

        groups = {}
        for role, permissions in ROLE_PERMISSIONS.items():
            group = Group.objects.create(name=f"{spec['site_name']} – {role}")
            group.permissions.set([get_permission(identifier) for identifier in permissions["model"]])

            for root in roots:
                for codename in permissions["page"]:
                    GroupPagePermission.objects.create(
                        group=group, page=root, permission=get_permission(f"wagtailcore.{codename}")
                    )

            for identifier in permissions["collection"]:
                GroupCollectionPermission.objects.create(
                    group=group, collection=collection, permission=get_permission(identifier)
                )

            for identifier in permissions.get("site", []):
                GroupSitePermission.objects.create(group=group, site=site, permission=get_permission(identifier))

            for shared_collection in shared_collections:
                GroupCollectionPermission.objects.create(
                    group=group,
                    collection=shared_collection,
                    permission=get_permission("wagtailimages.choose_image"),
                )

            groups[role] = group

        return groups

    def create_workflow(self, spec: dict, site: Site, groups: dict) -> None:
        workflow = Workflow.objects.create(name=f"Validation {spec['short_name']}")
        task = GroupApprovalTask.objects.create(name=f"Approbation {spec['short_name']}")
        task.groups.set([groups[MODERATORS], groups[ADMINISTRATORS]])
        WorkflowTask.objects.create(workflow=workflow, task=task, sort_order=0)

        home = site.root_page
        for root in [home] + list(home.get_translations()):
            WorkflowPage.objects.create(workflow=workflow, page=root)

    def create_users(self, password: str) -> None:
        self.result.users = create_demo_users(self.site_keys, password)
