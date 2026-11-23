from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.urls import reverse
from wagtail.images import get_image_model
from wagtail.images.permissions import permission_policy as image_permission_policy
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import (
    Collection,
    GroupApprovalTask,
    GroupCollectionPermission,
    GroupPagePermission,
    Page,
    Site,
    TaskState,
    Workflow,
)
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.blocks.medias import ImageBlockWithDefault
from sites_conformes.core.constants import DEFAULT_ILLUSTRATIONS_COLLECTION, DSFR_PICTOGRAMS_COLLECTION
from sites_conformes.core.models import CmsDsfrConfig, ContentPage
from sites_conformes.core.multisite_isolation import get_sites_for_user
from sites_conformes.core.services.accessors import (
    get_or_create_collection,
    get_or_create_content_page,
    get_or_create_footer_bottom_menu,
    get_or_create_main_menu,
)
from sites_conformes.core.services.sites import (
    ADMINISTRATORS,
    EDITORS,
    MODERATORS,
    SiteCreationError,
    create_site,
)
from sites_conformes.core.tests.base import ClearSiteRootPathsCacheMixin, MonositeTestCase, MultisiteTestCase
from sites_conformes.core.utils import get_default_site, get_installed_image
from sites_conformes.forms.models import FormPage
from sites_conformes.menus.models import FooterBottomMenu, MainMenu

Image = get_image_model()
User = get_user_model()

PICTOGRAM_TITLE = "Pictogrammes DSFR — Digital — Coding"
ILLUSTRATION_TITLE = "Illustration Sites Faciles Femme Ordinateur"


def create_installed_images() -> list:
    """
    Creates the collections imported at installation, with one image each, so that
    create_site doesn't import the static files.
    """
    pictogram = Image.objects.create(
        title=PICTOGRAM_TITLE,
        file=get_test_image_file(),
        collection=get_or_create_collection(DSFR_PICTOGRAMS_COLLECTION),
    )
    illustration = Image.objects.create(
        title=ILLUSTRATION_TITLE,
        file=get_test_image_file(),
        collection=get_or_create_collection(DEFAULT_ILLUSTRATIONS_COLLECTION),
    )
    return [pictogram, illustration]


def get_menu_items(menu) -> list:
    # Without the block ids, generated when the menu is loaded
    return [(block["type"], block["value"]) for block in menu.items.raw_data]


def get_site_state(site: Site) -> dict:
    """
    Everything create_site must not modify on another site.
    """
    home = site.root_page
    return {
        "site": (site.hostname, site.port, site.site_name, site.root_page_id, site.is_default_site),
        "homes": [
            (page.pk, page.title, page.slug, page.latest_revision_id) for page in [home, *home.get_translations()]
        ],
        "main_menus": sorted((menu.locale_id, get_menu_items(menu)) for menu in MainMenu.objects.filter(site=site)),
        "footer_menus": sorted(
            (menu.locale_id, get_menu_items(menu)) for menu in FooterBottomMenu.objects.filter(site=site)
        ),
        "config": list(CmsDsfrConfig.objects.filter(site=site).values()),
        "pages": list(
            Page.objects.descendant_of(home, inclusive=True).values_list("pk", "title", "slug", "latest_revision_id")
        ),
    }


def get_groups_state() -> dict:
    return {
        group.name: (
            sorted(group.permissions.values_list("pk", flat=True)),
            sorted(GroupPagePermission.objects.filter(group=group).values_list("page_id", "permission_id")),
            sorted(
                GroupCollectionPermission.objects.filter(group=group).values_list("collection_id", "permission_id")
            ),
        )
        for group in Group.objects.all()
    }


class CreateSiteTestsMixin:
    """
    Site C is created on top of the demo sites, in French and English.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.installed_images = create_installed_images()
        cls.other_sites = [site for site in [cls.site_a, cls.site_b] if site]
        cls.other_sites_state = {site.pk: get_site_state(site) for site in cls.other_sites}
        cls.groups_state = get_groups_state()
        cls.installed_image_count = Image.objects.filter(collection__name__in=cls.installed_collection_names()).count()

        cls.setup = create_site(hostname="site-c.localhost", name="Site C", language_codes=["fr", "en"])
        cls.site_c = cls.setup.site
        cls.home_c = cls.site_c.root_page.specific
        cls.home_c_en = cls.home_c.get_translations().get().specific

        cls.users_c = {}
        for username, role in [("admin-c", ADMINISTRATORS), ("moderateur-c", MODERATORS), ("editeur-c", EDITORS)]:
            user = User.objects.create_user(username=username, password="password")
            user.groups.add(cls.setup.groups[role])
            cls.users_c[username] = user

    @staticmethod
    def installed_collection_names() -> list:
        return [DSFR_PICTOGRAMS_COLLECTION, DEFAULT_ILLUSTRATIONS_COLLECTION]

    def get_user(self, username: str):
        # A fresh instance: the permissions are cached on the user object
        return User.objects.get(username=username)

    # Creation

    def test_site_is_created_with_its_home_page_and_translation(self):
        self.assertTrue(self.setup.created)
        self.assertEqual((self.site_c.hostname, self.site_c.site_name), ("site-c.localhost", "Site C"))
        self.assertFalse(self.site_c.is_default_site)

        self.assertEqual(self.home_c.get_parent().pk, Page.get_first_root_node().pk)
        self.assertEqual(self.home_c.slug, "site-c-localhost")
        self.assertEqual(self.home_c.locale.language_code, "fr")
        self.assertTrue(self.home_c.live)
        self.assertEqual(self.home_c_en.locale.language_code, "en")
        self.assertTrue(self.home_c_en.live)
        self.assertEqual([page.pk for page in self.setup.home_pages], [self.home_c.pk, self.home_c_en.pk])

    def test_site_responds_in_french_and_english(self):
        for path, language_code in [("/", "fr"), ("/en/", "en")]:
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_HOST="site-c.localhost")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["page"].locale.language_code, language_code)
                self.assertEqual(response.context["page"].get_site(), self.site_c)

    def test_collection_groups_and_workflow_are_created(self):
        self.assertEqual(self.setup.collection.name, "Site C")
        self.assertEqual(self.setup.collection.get_parent(), Collection.get_first_root_node())
        self.assertEqual(
            {group.name for group in self.setup.groups.values()},
            {"Site C – Administrateurs", "Site C – Modérateurs", "Site C – Éditeurs"},
        )

        workflow = self.setup.workflow
        self.assertEqual(workflow.name, "Validation Site C")
        task = workflow.tasks.get().specific
        self.assertEqual(task.name, "Approbation Site C")
        self.assertEqual(set(task.groups.all()), {self.setup.groups[MODERATORS], self.setup.groups[ADMINISTRATORS]})
        for home in [self.home_c, self.home_c_en]:
            self.assertEqual(home.get_workflow(), workflow)

    def test_menus_and_configuration_are_created_in_each_language(self):
        for home in [self.home_c, self.home_c_en]:
            with self.subTest(locale=home.locale.language_code):
                main_menu = MainMenu.objects.get(site=self.site_c, locale=home.locale)
                self.assertEqual([item.value["page"].pk for item in main_menu.items], [home.pk])
                footer_menu = FooterBottomMenu.objects.get(site=self.site_c, locale=home.locale)
                self.assertEqual(len(footer_menu.items), 0)

        menus = MainMenu.objects.filter(site=self.site_c)
        self.assertEqual(len({menu.translation_key for menu in menus}), 1)

        config = CmsDsfrConfig.objects.get(site=self.site_c)
        self.assertEqual(config.site_title, "Site C")
        self.assertEqual(config.language_selector_mode, "simple")

    def test_running_it_again_creates_no_duplicate(self):
        def counts():
            return {
                model.__name__: model.objects.count()
                for model in [
                    Site,
                    Page,
                    Collection,
                    Group,
                    GroupPagePermission,
                    GroupCollectionPermission,
                    Workflow,
                    GroupApprovalTask,
                    MainMenu,
                    FooterBottomMenu,
                    CmsDsfrConfig,
                    Image,
                ]
            }

        before = counts()
        setup = create_site(hostname="site-c.localhost", name="Site C", language_codes=["fr", "en"])
        self.assertFalse(setup.created)
        self.assertEqual(setup.site, self.site_c)
        self.assertEqual(counts(), before)

    def test_other_sites_are_not_modified(self):
        for site in self.other_sites:
            state = get_site_state(Site.objects.get(pk=site.pk))
            for key, value in self.other_sites_state[site.pk].items():
                with self.subTest(site=site.site_name, key=key):
                    self.assertEqual(state[key], value)

    def test_existing_groups_are_not_modified(self):
        groups_state = get_groups_state()
        for name, state in self.groups_state.items():
            with self.subTest(group=name):
                self.assertEqual(groups_state[name], state)

    # Permissions

    def test_page_permissions_follow_the_roles(self):
        expectations = {
            # can_edit, can_publish, can_delete (a page with sub-pages)
            "admin-c": (True, True, True),
            "moderateur-c": (True, True, False),
            "editeur-c": (True, False, False),
        }
        page = self.home_c.add_child(instance=ContentPage(title="Rubrique", slug="rubrique"))
        page.add_child(instance=ContentPage(title="Sous-page", slug="sous-page"))

        for username, (can_edit, can_publish, can_delete) in expectations.items():
            user = self.get_user(username)
            for tested_page in [self.home_c, self.home_c_en, page]:
                with self.subTest(username=username, page=tested_page.url_path):
                    permissions = tested_page.permissions_for_user(user)
                    self.assertEqual(permissions.can_edit(), can_edit)
                    self.assertEqual(permissions.can_add_subpage(), True)
                    self.assertEqual(permissions.can_publish(), can_publish)
            with self.subTest(username=username, delete=True):
                self.assertEqual(page.permissions_for_user(user).can_delete(), can_delete)

    def test_editor_cannot_add_pages_to_the_other_sites(self):
        user = self.get_user("editeur-c")
        for site in self.other_sites:
            with self.subTest(site=site.site_name):
                self.assertFalse(site.root_page.permissions_for_user(user).can_add_subpage())

    def test_model_permissions_follow_the_roles(self):
        expectations = {
            "sites_conformes_menus.change_mainmenu": {"admin-c", "moderateur-c"},
            "wagtailredirects.change_redirect": {"admin-c"},
            "sites_conformes_blog.change_category": {"admin-c", "moderateur-c", "editeur-c"},
            "wagtailadmin.access_admin": {"admin-c", "moderateur-c", "editeur-c"},
            # The accounts are managed by the superadmins
            "auth.change_user": set(),
            "wagtailcore.add_workflow": set(),
        }
        for permission, usernames in expectations.items():
            for username in self.users_c:
                with self.subTest(permission=permission, username=username):
                    self.assertEqual(self.get_user(username).has_perm(permission), username in usernames)

    def test_only_administrators_edit_the_settings_of_the_site(self):
        url = reverse("wagtailsettings:edit", args=["sites_conformes_core", "cmsdsfrconfig", self.site_c.pk])
        for username, status_code in [("admin-c", 200), ("moderateur-c", 302), ("editeur-c", 302)]:
            with self.subTest(username=username):
                self.client.force_login(self.get_user(username))
                response = self.client.get(url, HTTP_HOST="site-c.localhost")
                self.assertEqual(response.status_code, status_code)

        if self.other_sites:
            self.client.force_login(self.get_user("admin-c"))
            other_url = reverse(
                "wagtailsettings:edit", args=["sites_conformes_core", "cmsdsfrconfig", self.other_sites[0].pk]
            )
            self.assertEqual(self.client.get(other_url, HTTP_HOST="site-c.localhost").status_code, 302)

    def test_images_are_added_to_the_collection_of_the_site_only(self):
        for username in self.users_c:
            with self.subTest(username=username):
                collections = image_permission_policy.collections_user_has_permission_for(
                    self.get_user(username), "add"
                )
                self.assertEqual(list(collections), [self.setup.collection])

    def test_installed_images_can_be_chosen_but_not_modified(self):
        for username in self.users_c:
            user = self.get_user(username)
            for image in self.installed_images:
                with self.subTest(username=username, image=image.title):
                    choosable = image_permission_policy.instances_user_has_permission_for(user, "choose")
                    self.assertIn(image, choosable)
                    for action in ["change", "delete"]:
                        self.assertFalse(image_permission_policy.user_has_permission_for_instance(user, action, image))

    def test_installed_images_cannot_be_modified_through_their_url(self):
        image = self.installed_images[0]
        for username in self.users_c:
            with self.subTest(username=username):
                self.client.force_login(self.get_user(username))
                response = self.client.get(reverse("wagtailimages:edit", args=[image.pk]))
                self.assertNotEqual(response.status_code, 200)
                self.client.post(reverse("wagtailimages:delete", args=[image.pk]))
                self.assertTrue(Image.objects.filter(pk=image.pk).exists())

        self.client.force_login(self.users["superadmin"])
        self.assertEqual(self.client.get(reverse("wagtailimages:edit", args=[image.pk])).status_code, 200)

    def test_installed_images_are_not_imported_again(self):
        count = Image.objects.filter(collection__name__in=self.installed_collection_names()).count()
        self.assertEqual(count, self.installed_image_count)

    # Workflow

    def test_submitted_page_is_reviewed_by_the_site_moderators_and_administrators_only(self):
        editor = self.get_user("editeur-c")
        for home in [self.home_c, self.home_c_en]:
            with self.subTest(locale=home.locale.language_code):
                page = home.add_child(instance=ContentPage(title="Nouvelle page", slug="nouvelle-page", live=False))
                page.save_revision(user=editor)
                workflow = page.get_workflow()
                self.assertEqual(workflow, self.setup.workflow)
                workflow_state = workflow.start(page, editor)
                task_state = workflow_state.current_task_state

                for username in ["admin-c", "moderateur-c"]:
                    self.assertIn(task_state, TaskState.objects.reviewable_by(self.get_user(username)))
                self.assertNotIn(task_state, TaskState.objects.reviewable_by(editor))
                for username in ["moderateur-a", "admin-a", "moderateur-b"]:
                    if username in self.users:
                        self.assertNotIn(task_state, TaskState.objects.reviewable_by(self.users[username]))

    # Options

    def test_a_language_added_later_gets_the_permissions_and_the_workflow(self):
        setup = create_site(hostname="site-d.localhost", name="Site D")
        self.assertEqual(len(setup.home_pages), 1)

        setup = create_site(hostname="site-d.localhost", name="Site D", language_codes=["fr", "en"])
        home_en = setup.site.root_page.get_translations().get()
        self.assertEqual(setup.home_pages[1], home_en)
        self.assertEqual(home_en.get_workflow(), setup.workflow)
        for role, group in setup.groups.items():
            with self.subTest(role=role):
                self.assertTrue(GroupPagePermission.objects.filter(group=group, page=home_en).exists())

    def test_starter_pages_are_created_below_the_site(self):
        setup = create_site(hostname="site-d.localhost", name="Site D", with_starter_pages=True)
        home = Page.objects.get(pk=setup.site.root_page_id)

        for slug in ["mentions-legales", "accessibilite", "contact"]:
            with self.subTest(slug=slug):
                page = home.get_children().get(slug=slug)
                self.assertEqual(page.get_site(), setup.site)
        self.assertIsInstance(home.get_children().get(slug="contact").specific, FormPage)

        footer_menu = FooterBottomMenu.objects.get(site=setup.site)
        self.assertEqual(len(footer_menu.items), 2)
        main_menu = MainMenu.objects.get(site=setup.site)
        self.assertEqual([item.value["page"].slug for item in main_menu.items], [home.slug, "contact"])

        for site in self.other_sites:
            with self.subTest(site=site.site_name):
                self.assertEqual(get_site_state(Site.objects.get(pk=site.pk)), self.other_sites_state[site.pk])

    def test_existing_site_keeps_its_name(self):
        setup = create_site(hostname="site-c.localhost", name="Autre nom")
        self.assertEqual(setup.site.site_name, "Site C")
        self.assertEqual(setup.groups[EDITORS].name, "Site C – Éditeurs")
        self.assertTrue(any("Autre nom" not in warning and "Site C" in warning for warning in setup.warnings))

    # Parameters and warnings

    def test_invalid_parameters_are_refused(self):
        for kwargs in [
            {"hostname": "https://site-d.localhost", "name": "Site D"},
            {"hostname": "site-d.localhost:8000", "name": "Site D"},
            {"hostname": "site-d.localhost", "name": " "},
            {"hostname": "site-d.localhost", "name": "Site D", "language_codes": ["fr", "xx"]},
        ]:
            with self.subTest(**kwargs):
                with self.assertRaises(SiteCreationError):
                    create_site(**kwargs)
        self.assertFalse(Site.objects.filter(hostname="site-d.localhost").exists())

    @override_settings(ALLOWED_HOSTS=["site-a.localhost"])
    def test_hostname_outside_allowed_hosts_is_created_with_a_warning(self):
        setup = create_site(hostname="site-d.localhost", name="Site D")
        self.assertTrue(setup.created)
        self.assertTrue(any("ALLOWED_HOSTS" in warning for warning in setup.warnings))

    def test_hostname_in_allowed_hosts_has_no_warning(self):
        self.assertFalse(any("ALLOWED_HOSTS" in warning for warning in self.setup.warnings))

    def test_command_creates_the_site_and_prints_the_warnings(self):
        stdout = StringIO()
        with override_settings(ALLOWED_HOSTS=["site-a.localhost"]):
            call_command("create_site", hostname="site-d.localhost", name="Site D", locales="fr,en", stdout=stdout)
        output = stdout.getvalue()
        self.assertIn("Site « Site D » créé", output)
        self.assertIn("Site D – Éditeurs", output)
        self.assertIn("Attention : « site-d.localhost » n’est pas dans ALLOWED_HOSTS", output)

        stdout = StringIO()
        call_command("create_site", hostname="site-d.localhost", name="Site D", stdout=stdout)
        self.assertIn("déjà existant", stdout.getvalue())

    def test_command_refuses_unknown_languages(self):
        with self.assertRaises(CommandError):
            call_command("create_site", hostname="site-d.localhost", name="Site D", locales="fr,xx", stdout=StringIO())

    def test_set_config_only_modifies_the_default_site(self):
        default_site = get_default_site()
        with override_settings(HOST_URL="nouveau.localhost", HOST_PORT="8123"):
            call_command("set_config", stdout=StringIO())
        default_site.refresh_from_db()
        self.assertEqual((default_site.hostname, default_site.port), ("nouveau.localhost", 8123))
        self.site_c.refresh_from_db()
        self.assertEqual(self.site_c.hostname, "site-c.localhost")


class MonositeCreateSiteTestCase(CreateSiteTestsMixin, MonositeTestCase):
    def test_warns_that_the_isolation_is_disabled(self):
        self.assertTrue(any("cloisonnement multisite est désactivé" in warning for warning in self.setup.warnings))

    def test_lists_the_groups_without_page_permission(self):
        Group.objects.create(name="Groupe sans page")
        setup = create_site(hostname="site-c.localhost", name="Site C")
        warning = next(warning for warning in setup.warnings if "sans droit de page" in warning)
        self.assertIn("Groupe sans page", warning)
        self.assertNotIn("Site C", warning)


class MultisiteCreateSiteTestCase(CreateSiteTestsMixin, MultisiteTestCase):
    def test_no_isolation_warning(self):
        self.assertFalse(any("cloisonnement" in warning for warning in self.setup.warnings))

    def test_editor_of_a_and_c_sees_both_sites(self):
        user = self.get_user("editeur-a")
        user.groups.add(self.setup.groups[EDITORS])
        self.assertEqual(set(get_sites_for_user(user)), {self.site_a, self.site_c})

    def test_default_block_image_ignores_the_images_of_the_sites(self):
        # An image of site A with the title of a default illustration, created last
        Image.objects.create(
            title=ILLUSTRATION_TITLE,
            file=get_test_image_file(),
            collection=Collection.objects.get(name=self.site_a.site_name),
        )
        block = ImageBlockWithDefault(default_image_title=ILLUSTRATION_TITLE)
        self.assertEqual(block.get_default().pk, self.installed_images[1].pk)
        self.assertEqual(get_installed_image(ILLUSTRATION_TITLE).pk, self.installed_images[1].pk)


class InstalledImagesTestCase(ClearSiteRootPathsCacheMixin, WagtailPageTestCase):
    def test_site_image_is_never_a_default_image(self):
        Image.objects.create(title=ILLUSTRATION_TITLE, file=get_test_image_file())
        self.assertIsNone(get_installed_image(ILLUSTRATION_TITLE))
        self.assertIsNone(ImageBlockWithDefault(default_image_title=ILLUSTRATION_TITLE).get_default())

    def test_installed_images_are_imported_only_if_missing(self):
        with mock.patch("sites_conformes.core.services.sites.call_command") as call_command_mock:
            create_installed_images()
            create_site(hostname="site-c.localhost", name="Site C")
        call_command_mock.assert_not_called()

        Collection.objects.filter(name=DEFAULT_ILLUSTRATIONS_COLLECTION).delete()
        with (
            mock.patch("sites_conformes.core.services.sites.call_command") as call_command_mock,
            mock.patch("sites_conformes.core.services.sites.os.path.isdir", return_value=True),
        ):
            create_site(hostname="site-c.localhost", name="Site C")
        self.assertEqual([call.args[0] for call in call_command_mock.call_args_list], ["import_illustration_images"])


def skip_image_imports(name, *args, **kwargs):
    if name not in ("import_dsfr_pictograms", "import_illustration_images"):
        call_command(name, *args, **kwargs)


@mock.patch("sites_conformes.core.management.commands.create_starter_pages.call_command", skip_image_imports)
class CreateStarterPagesTestCase(ClearSiteRootPathsCacheMixin, WagtailPageTestCase):
    def test_new_instance_without_site_parameter(self):
        call_command("create_starter_pages", stdout=StringIO())

        site = get_default_site()
        home = site.root_page
        self.assertEqual(home.slug, "home")
        self.assertEqual(home.title, "Votre nouveau site avec Sites Conformes")
        self.assertEqual(
            sorted(home.get_children().values_list("slug", flat=True)),
            ["accessibilite", "contact", "mentions-legales"],
        )
        self.assertEqual(len(FooterBottomMenu.objects.get(site=site).items), 2)
        self.assertEqual(
            [item.value["page"].slug for item in MainMenu.objects.get(site=site).items], ["home", "contact"]
        )

    def test_instance_with_pages_without_site_parameter(self):
        call_command("create_starter_pages", stdout=StringIO())
        count = Page.objects.count()

        stdout = StringIO()
        call_command("create_starter_pages", stdout=stdout)
        self.assertIn("already have pages", stdout.getvalue())
        self.assertEqual(Page.objects.count(), count)

    def test_site_parameter_creates_the_pages_below_the_site(self):
        call_command("create_starter_pages", stdout=StringIO())
        default_site = get_default_site()
        default_pages = list(Page.objects.values_list("pk", "title", "slug"))
        create_installed_images()
        site = create_site(hostname="site-c.localhost", name="Site C").site

        call_command("create_starter_pages", site=site.pk, stdout=StringIO())

        self.assertEqual(
            sorted(Page.objects.get(pk=site.root_page_id).get_children().values_list("slug", flat=True)),
            ["accessibilite", "contact", "mentions-legales"],
        )
        self.assertTrue(set(default_pages) <= set(Page.objects.values_list("pk", "title", "slug")))
        self.assertEqual(len(FooterBottomMenu.objects.get(site=default_site).items), 2)

        # Idempotent
        count = Page.objects.count()
        call_command("create_starter_pages", site=site.pk, stdout=StringIO())
        self.assertEqual(Page.objects.count(), count)

    def test_site_parameter_refuses_the_home_page(self):
        with self.assertRaises(CommandError):
            call_command("create_starter_pages", site=get_default_site().pk, slug=["home"], stdout=StringIO())


class AccessorsSiteParameterTestCase(ClearSiteRootPathsCacheMixin, WagtailPageTestCase):
    def test_pages_and_menus_are_looked_up_in_the_given_site(self):
        default_page = get_or_create_content_page("actualites", title="Actualités", body=[])
        create_installed_images()
        site = create_site(hostname="site-c.localhost", name="Site C").site

        page = get_or_create_content_page("actualites", title="Actualités C", body=[], site=site)
        self.assertNotEqual(page.pk, default_page.pk)
        self.assertEqual(page.get_parent().pk, site.root_page.pk)
        self.assertEqual(get_or_create_content_page("actualites", title="", body=[]).pk, default_page.pk)
        self.assertEqual(get_or_create_content_page("actualites", title="", body=[], site=site).pk, page.pk)

        self.assertEqual(get_or_create_main_menu(site).site, site)
        self.assertEqual(get_or_create_footer_bottom_menu(site).site, site)
        self.assertEqual(get_or_create_main_menu().site, get_default_site())
