from wagtail.models import Page, Site
from wagtail.test.utils import WagtailPageTestCase

from content_manager.models import ContentPage
from menus.models import FooterBottomMenu, MainMenu, TopMenu


class TopMenuLinkBlockTestCase(WagtailPageTestCase):
    """Tests for MenuLinkWithIconBlock rendered via header_top_menu.html / link.html."""

    def setUp(self):
        home = Page.objects.get(slug="home")
        self.site = Site.objects.get(is_default_site=True)
        self.content_page = home.add_child(instance=ContentPage(title="Page de test", slug="test-page"))
        self.content_page.save()
        self.top_menu = TopMenu.objects.create(site=self.site)

    def test_external_link(self):
        self.top_menu.items = [
            ("link", {"text": "Info Gouv", "external_url": "https://info.gouv.fr", "link_type": "external_url"})
        ]
        self.top_menu.save()

        response = self.client.get(self.content_page.url)
        html = response.content.decode()

        # class omitted: it has variable empty parts (size, icon_class) that produce trailing spaces
        self.assertInHTML(
            """
            <a target="_blank"
               rel="noopener external"
               title="info.gouv.fr - Ouvre une nouvelle fenêtre"
               id="footer__content-link-gouvernement"
               class="fr-footer__content-link"
               href="https://www.info.gouv.fr">info.gouv.fr</a>
            """,
            html,
        )

    def test_page_link(self):
        self.top_menu.items = [("link", {"text": "Page de test", "page": self.content_page, "link_type": "page"})]
        self.top_menu.save()

        response = self.client.get(self.content_page.url)
        html = response.content.decode()

        self.assertInHTML(
            f'<a class="fr-btn" href="{self.content_page.url}" aria-current="page">Page de test</a>', html
        )
        self.assertNotInHTML(
            f"""<a class="fr-btn" href="{self.content_page.url}"
            target="_blank" aria-current="page">Page de test</a>""",
            html,
        )


class FooterBottomMenuLinkBlockTestCase(WagtailPageTestCase):
    """Tests for FooterBottomLinkBlock rendered via footer_bottom_menu.html / footer_bottom_link.html."""

    def setUp(self):
        home = Page.objects.get(slug="home")
        self.site = Site.objects.get(is_default_site=True)
        self.content_page = home.add_child(instance=ContentPage(title="Page de test", slug="test-page"))
        self.content_page.save()
        self.footer_menu = FooterBottomMenu.objects.create(site=self.site)

    def test_external_link(self):
        self.footer_menu.items = [
            (
                "link",
                {"text": "Mentions légales", "external_url": "https://info.gouv.fr", "link_type": "external_url"},
            )
        ]
        self.footer_menu.save()

        response = self.client.get(self.content_page.url)
        html = response.content.decode()

        self.assertInHTML(
            '<a class="fr-footer__bottom-link" href="https://info.gouv.fr" target="_blank" rel="noopener noreferrer">'
            "Mentions légales"
            '<span class="fr-sr-only">Ouvre une nouvelle fenêtre</span>'
            "</a>",
            html,
        )

    def test_page_link(self):

        response = self.client.get(self.content_page.url)
        html = response.content.decode()

        self.assertInHTML(
            """<a class="fr-footer__bottom-link" href="/plan-du-site/">Plan du site</a>""",
            html,
        )


class MainMenuLinkBlockTestCase(WagtailPageTestCase):
    """Tests for MainMenuLinkBlock rendered via header_main_menu.html / main_menu_link.html."""

    def setUp(self):
        home = Page.objects.get(slug="home")
        self.site = Site.objects.get(is_default_site=True)
        self.content_page = home.add_child(instance=ContentPage(title="Page de test", slug="test-page"))
        self.content_page.save()
        self.main_menu = MainMenu.objects.create(site=self.site)

    def test_external_link(self):
        self.main_menu.items = [
            ("link", {"text": "Info Gouv", "external_url": "https://info.gouv.fr", "link_type": "external_url"})
        ]
        self.main_menu.save()

        response = self.client.get(self.content_page.url)
        html = response.content.decode()

        self.assertInHTML(
            '<a class="fr-nav__link" href="https://info.gouv.fr" target="_blank" rel="noopener noreferrer">'
            "Info Gouv"
            '<span class="fr-sr-only">Ouvre une nouvelle fenêtre</span>'
            "</a>",
            html,
        )

    def test_page_link(self):
        self.main_menu.items = [("link", {"text": "Page de test", "page": self.content_page, "link_type": "page"})]
        self.main_menu.save()

        response = self.client.get(self.content_page.url)
        html = response.content.decode()

        self.assertInHTML(
            f'<a class="fr-nav__link" href="{self.content_page.url}" aria-current="page">Page de test</a>',
            html,
        )

        self.assertNotInHTML(
            f"""<a class="fr-nav__link" href="{self.content_page.url}"
            target="_blank" aria-current="page">Page de test</a>""",
            html,
        )


class MainMenuSubmenuBlockTestCase(WagtailPageTestCase):
    """Tests for MainMenuSubmenuBlock rendered via main_menu_submenu.html."""

    def setUp(self):
        home = Page.objects.get(slug="home")
        self.site = Site.objects.get(is_default_site=True)
        self.linked_page = home.add_child(instance=ContentPage(title="Page liée", slug="linked-page"))
        self.linked_page.save()
        self.other_page = home.add_child(instance=ContentPage(title="Autre page", slug="other-page"))
        self.other_page.save()
        self.main_menu = MainMenu.objects.create(site=self.site)
        self.main_menu.items = [
            (
                "submenu",
                {
                    "label": "Mon sous-menu",
                    "links": [("link", {"text": "Page liée", "page": self.linked_page, "link_type": "page"})],
                },
            )
        ]
        self.main_menu.save()

    def test_submenu_button(self):
        response = self.client.get(self.other_page.url)
        html = response.content.decode()

        self.assertInHTML(
            '<button aria-expanded="false" aria-controls="collapse-menu-mon-sous-menu"'
            ' type="menu" class="fr-nav__btn">Mon sous-menu</button>',
            html,
        )

    def test_submenu_collapse_div_contains_link(self):
        response = self.client.get(self.other_page.url)
        html = response.content.decode()

        self.assertInHTML(
            '<div class="fr-collapse fr-menu" id="collapse-menu-mon-sous-menu">'
            '<ul class="fr-menu__list">'
            '<li class="fr-nav__item">'
            f'<a class="fr-nav__link" href="{self.linked_page.url}">Page liée</a>'
            "</li>"
            "</ul>"
            "</div>",
            html,
        )

    def test_submenu_button_has_aria_current_when_on_linked_page(self):
        response = self.client.get(self.linked_page.url)
        html = response.content.decode()

        self.assertInHTML(
            '<button aria-current="true" aria-expanded="false" aria-controls="collapse-menu-mon-sous-menu"'
            ' type="menu" class="fr-nav__btn">Mon sous-menu</button>',
            html,
        )

    def test_submenu_button_has_no_aria_current_when_on_other_page(self):
        response = self.client.get(self.other_page.url)
        html = response.content.decode()

        self.assertNotInHTML(
            '<button aria-current="true" class="fr-nav__btn">Mon sous-menu</button>',
            html,
        )


class MainMenuMegamenuBlockTestCase(WagtailPageTestCase):
    """Tests for MainMenuMegamenuBlock rendered via main_menu_megamenu.html."""

    def setUp(self):
        home = Page.objects.get(slug="home")
        self.site = Site.objects.get(is_default_site=True)
        self.column_page = home.add_child(instance=ContentPage(title="Page de colonne", slug="column-page"))
        self.column_page.save()
        self.other_page = home.add_child(instance=ContentPage(title="Autre page", slug="other-page"))
        self.other_page.save()
        self.section_page = home.add_child(instance=ContentPage(title="Voir la section", slug="section-page"))
        self.section_page.save()
        self.main_menu = MainMenu.objects.create(site=self.site)
        self.main_menu.items = [
            (
                "megamenu",
                {
                    "label": "Ma section",
                    "description": "Description de la section",
                    "main_link": {
                        "text": "Voir la section",
                        "page": self.section_page,
                        "link_type": "page",
                    },
                    "columns": [
                        (
                            "column",
                            {
                                "label": "Colonne 1",
                                "links": [
                                    (
                                        "link",
                                        {"text": "Page de colonne", "page": self.column_page, "link_type": "page"},
                                    )
                                ],
                            },
                        )
                    ],
                },
            )
        ]
        self.main_menu.save()

    def test_megamenu_button(self):
        response = self.client.get(self.other_page.url)
        html = response.content.decode()

        self.assertInHTML(
            '<button aria-expanded="false" aria-controls="collapse-menu-ma-section"'
            ' type="menu" class="fr-nav__btn">Ma section</button>',
            html,
        )

    def test_megamenu_leader_section(self):
        response = self.client.get(self.other_page.url)
        html = response.content.decode()

        self.assertInHTML(
            f"""
            <div class="fr-mega-menu__leader">
            <h4 class="fr-h4 fr-mb-2v">Ma section</h4>
            <p class="fr-hidden fr-displayed-lg">Description de la section</p>
            <a class="fr-link fr-fi-arrow-right-line fr-link--icon-right fr-link--align-on-content"
                          href="{self.section_page.url}">Voir la section</a>
            </div>""",
            html,
        )

    def test_megamenu_column_with_link(self):
        response = self.client.get(self.other_page.url)
        html = response.content.decode()

        self.assertInHTML(
            '<div class="fr-col-12 fr-col-lg-3">'
            '<h5 class="fr-mega-menu__category"><a class="fr-nav__link" href="#" target="_self">Colonne 1</a></h5>'
            '<ul class="fr-menu__list">'
            "<li>"
            f'<a class="fr-nav__link" href="{self.column_page.url}">Page de colonne</a>'
            "</li>"
            "</ul>"
            "</div>",
            html,
        )

    def test_megamenu_button_has_aria_current_when_on_column_linked_page(self):
        response = self.client.get(self.column_page.url)
        html = response.content.decode()

        self.assertInHTML(
            '<button aria-current="true" aria-expanded="false" aria-controls="collapse-menu-ma-section"'
            ' type="menu" class="fr-nav__btn">Ma section</button>',
            html,
        )

    def test_megamenu_button_has_no_aria_current_when_on_other_page(self):
        response = self.client.get(self.other_page.url)
        html = response.content.decode()

        self.assertNotInHTML(
            '<button aria-current="true" class="fr-nav__btn">Ma section</button>',
            html,
        )

    def test_megamenu_close_button(self):
        response = self.client.get(self.other_page.url)
        html = response.content.decode()

        self.assertInHTML(
            '<button class="fr-link--close fr-link" aria-controls="collapse-menu-ma-section"'
            ' data-fr-js-collapse-button="true">Fermer</button>',
            html,
        )
