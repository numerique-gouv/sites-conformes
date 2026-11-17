from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.translation import gettext
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.models import CatalogIndexPage, Category, CmsDsfrConfig, ContentPage, Tag
from sites_conformes.core.services.accessors import get_or_create_content_page

User = get_user_model()


class ContentPageTestCase(WagtailPageTestCase):
    def setUp(self):
        home_page = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()
        self.public_content_page = home_page.add_child(
            instance=ContentPage(
                title="Page de contenu publique",
                slug="public-content-page",
                owner=self.admin,
            )
        )
        self.public_content_page.save()
        self.private_content_page = get_or_create_content_page(
            "private-content-page",
            title="Page de contenu privée",
            body=[("subpageslist", None)],
            parent_page=home_page,
            restriction_type="login",
        )
        self.private_content_page.save()

    def test_content_page_is_renderable(self):
        self.assertPageIsRenderable(self.public_content_page)

    def test_content_page_has_minimal_content(self):
        response = self.client.get(self.public_content_page.url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "<title>Page de contenu publique — Titre du site</title>",
        )

    def test_public_content_page_is_in_the_site_map(self):
        url = reverse("readable_sitemap")
        response = self.client.get(url)

        self.assertContains(
            response,
            """<a href="/public-content-page/">Page de contenu publique</a>""",
        )

    def test_private_content_page_is_not_rendered_when_logged_out(self):
        response = self.client.get(self.private_content_page.url)
        self.assertEqual(response.status_code, 302)

    def test_private_content_page_is_not_in_the_site_map_when_logged_out(self):
        url = reverse("readable_sitemap")
        response = self.client.get(url)

        self.assertNotContains(
            response,
            """<a href="/private-content-page/">Page de contenu privée</a>""",
        )

    def test_private_content_page_is_in_the_site_map_when_logged_in(self):
        self.client.login(username="test", password="pass")
        url = reverse("readable_sitemap")
        response = self.client.get(url)

        self.assertContains(
            response,
            """<a href="/private-content-page/">Page de contenu privée</a>""",
        )

    def test_excluded_page_is_not_in_readable_sitemap(self):
        home_page = Page.objects.get(slug="home")
        excluded_page = home_page.add_child(
            instance=ContentPage(
                title="Page exclue du plan du site",
                slug="excluded-page",
                owner=self.admin,
                exclude_from_sitemap=True,
            )
        )
        excluded_page.save()

        url = reverse("readable_sitemap")
        response = self.client.get(url)

        self.assertNotContains(
            response,
            """<a href="/excluded-page/">Page exclue du plan du site</a>""",
        )

        # Re-including the page restores it in the readable sitemap
        excluded_page.exclude_from_sitemap = False
        excluded_page.save()
        response = self.client.get(url)
        self.assertContains(
            response,
            """<a href="/excluded-page/">Page exclue du plan du site</a>""",
        )

    def test_excluded_page_is_not_in_xml_sitemap(self):
        home_page = Page.objects.get(slug="home")
        excluded_page = home_page.add_child(
            instance=ContentPage(
                title="Page exclue du sitemap XML",
                slug="excluded-xml-page",
                owner=self.admin,
                exclude_from_sitemap=True,
            )
        )
        excluded_page.save()

        url = reverse("xml_sitemap")
        response = self.client.get(url)

        self.assertNotContains(response, "/excluded-xml-page/")

        # Re-including the page restores it in the XML sitemap
        excluded_page.exclude_from_sitemap = False
        excluded_page.save()
        response = self.client.get(url)
        self.assertContains(response, "/excluded-xml-page/")

    def test_excluded_page_has_noindex_meta_tag(self):
        home_page = Page.objects.get(slug="home")
        excluded_page = home_page.add_child(
            instance=ContentPage(
                title="Page avec noindex",
                slug="noindex-page",
                owner=self.admin,
                exclude_from_sitemap=True,
            )
        )
        excluded_page.save()

        response = self.client.get(excluded_page.url)
        self.assertContains(response, '<meta name="robots" content="noindex" />')

        # Re-including the page removes the noindex meta tag
        excluded_page.exclude_from_sitemap = False
        excluded_page.save()
        response = self.client.get(excluded_page.url)
        self.assertNotContains(response, '<meta name="robots" content="noindex"')

    def test_normal_page_does_not_have_noindex_meta_tag(self):
        response = self.client.get(self.public_content_page.url)
        self.assertNotContains(response, '<meta name="robots" content="noindex"')

    def test_public_content_page_is_in_xml_sitemap(self):
        url = reverse("xml_sitemap")
        response = self.client.get(url)
        self.assertContains(response, "/public-content-page/")

    def test_exclude_from_sitemap_defaults_to_false(self):
        self.assertFalse(self.public_content_page.exclude_from_sitemap)

    def test_excluded_page_with_children_is_not_in_readable_sitemap(self):
        home_page = Page.objects.get(slug="home")
        excluded_parent = home_page.add_child(
            instance=ContentPage(
                title="Parent exclu",
                slug="excluded-parent",
                owner=self.admin,
                exclude_from_sitemap=True,
            )
        )
        excluded_parent.add_child(
            instance=ContentPage(
                title="Enfant de parent exclu",
                slug="child-of-excluded",
                owner=self.admin,
            )
        )
        url = reverse("readable_sitemap")
        response = self.client.get(url)
        self.assertNotContains(
            response,
            """<a href="/excluded-parent/">Parent exclu</a>""",
        )
        # Children are also hidden because the recursive include is inside the exclusion check
        self.assertNotContains(
            response,
            """<a href="/excluded-parent/child-of-excluded/">Enfant de parent exclu</a>""",
        )


class ConfigTestCase(WagtailPageTestCase):
    def setUp(self):
        home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()
        self.content_page = home.add_child(
            instance=ContentPage(
                title="Page de contenu",
                slug="content-page",
                owner=self.admin,
            )
        )
        self.content_page.save()

        self.config, _created = CmsDsfrConfig.objects.update_or_create(
            site_id=1,
            defaults={
                "site_title": "Site title",
                "site_tagline": "Site tagline",
                "header_brand": "République française",
                "header_brand_html": "République<br />française",
                "footer_brand": "République française",
                "footer_brand_html": "République<br />française",
                "footer_description": "Site <b>description</b>.",
            },
        )
        self.config.save()

    def test_header_brand_block_uses_conf(self):
        url = self.content_page.url
        response = self.client.get(url)

        self.assertInHTML(
            """<p class="fr-logo">République<br />française</p>""",
            response.content.decode(),
        )

    def test_footer_brand_block_uses_conf(self):
        url = self.content_page.url
        response = self.client.get(url)

        self.assertInHTML(
            """<div class="fr-footer__brand fr-enlarge-link">
                    <a id="footer-operator"
                    href="/"
                    title="Retourner à l’accueil - Site title - République française">
                    <p class="fr-logo">
                        République<br />française
                    </p>
                </a>
            </div>""",
            response.content.decode(),
        )

    def test_header_title_block_uses_conf(self):
        url = self.content_page.url
        response = self.client.get(url)

        self.assertInHTML(
            """<div class="fr-header__service">
                <a href="/" title="Accueil — Site title">
                    <p class="fr-header__service-title">Site title</p>
                </a>
                <p class="fr-header__service-tagline">Site tagline</p>
            </div>""",
            response.content.decode(),
        )

    def test_notice_is_not_set_by_default(self):
        url = self.content_page.url
        response = self.client.get(url)

        self.assertNotContains(
            response,
            "fr-notice__body",
        )

    def test_notice_can_be_set(self):
        self.config.notice_title = "Ceci est une information <b>importante</b> et <i>temporaire</i>."
        self.config.save()

        url = self.content_page.url
        response = self.client.get(url)

        self.assertContains(response, self.config.notice_title)

    def test_beta_tag_is_not_set_by_default(self):
        url = self.content_page.url
        response = self.client.get(url)

        self.assertNotContains(
            response,
            '<span class="fr-badge fr-badge--sm fr-badge--green-emeraude">BETA</span>',
        )

    def test_beta_tag_can_be_set(self):
        self.config.beta_tag = True
        self.config.save()

        url = self.content_page.url
        response = self.client.get(url)

        self.assertContains(
            response,
            '<span class="fr-badge fr-badge--sm fr-badge--green-emeraude">BETA</span>',
        )

    def test_footer_description_uses_conf(self):
        url = self.content_page.url
        response = self.client.get(url)

        self.config.refresh_from_db()

        self.assertContains(response, self.config.footer_description)


class CatalogIndexPageTestCase(WagtailPageTestCase):
    def setUp(self):
        home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()
        self.catalog_index_page = home.add_child(
            instance=CatalogIndexPage(
                title="Index de catalogue",
                slug="catalog-index",
                owner=self.admin,
            )
        )
        self.catalog_index_page.save()

        # Create tags
        self.tag1 = Tag.objects.create(name="Tag 1", slug="tag-1")
        self.tag2 = Tag.objects.create(name="Tag 2", slug="tag-2")

        # Create entries
        self.entry1 = self.catalog_index_page.add_child(
            instance=ContentPage(title="Entrée 1", slug="entry-1", owner=self.admin)
        )
        self.entry1.tags.add(self.tag1)
        self.entry1.save()

        self.entry2 = self.catalog_index_page.add_child(
            instance=ContentPage(title="Entrée 2", slug="entry-2", owner=self.admin)
        )
        self.entry2.tags.add(self.tag2)
        self.entry2.save()

        self.entry3 = self.catalog_index_page.add_child(
            instance=ContentPage(title="Entrée 3", slug="entry-3", owner=self.admin)
        )
        self.entry3.tags.add(self.tag1, self.tag2)
        self.entry3.save()

        self.entry4 = self.catalog_index_page.add_child(
            instance=ContentPage(title="Entrée 4", slug="entry-4", owner=self.admin)
        )
        self.entry4.save()

    def test_catalog_index_page_tags_list(self):
        response = self.client.get(self.catalog_index_page.url + "tags/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["sorted_tags"].keys()), ["T"])
        self.assertEqual([t.slug for t in response.context["sorted_tags"]["T"]], ["tag-1", "tag-2"])

    def test_catalog_index_page_is_renderable(self):
        self.assertPageIsRenderable(self.catalog_index_page)

    def test_catalog_index_page_has_minimal_content(self):
        url = self.catalog_index_page.url
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertInHTML(
            "<title>Index de catalogue — Titre du site</title>",
            response.content.decode(),
        )

        self.assertContains(response, "Entrée 1")
        self.assertContains(response, "Entrée 2")
        self.assertContains(response, "Entrée 3")
        self.assertContains(response, "Entrée 4")

    def test_single_filter(self):
        self.catalog_index_page.filter_selection = CatalogIndexPage.SINGLE_FILTER
        self.catalog_index_page.save()

        url = self.catalog_index_page.url + "?tag=tag-1"
        response = self.client.get(url)

        self.assertContains(response, "Entrée 1")
        self.assertNotContains(response, "Entrée 2")
        self.assertContains(response, "Entrée 3")
        self.assertNotContains(response, "Entrée 4")

    def test_single_filter_can_be_unselected(self):
        self.catalog_index_page.filter_selection = CatalogIndexPage.SINGLE_FILTER
        self.catalog_index_page.save()

        url = self.catalog_index_page.url + "?tag=tag-1"
        response = self.client.get(url)

        self.assertEqual(response.context["current_tag"], self.tag1)

        # Clicking the already-selected tag again must remove it from the URL
        # (toggle_url_filter relies on "current_tag" to detect this), instead
        # of re-adding it and leaving the filter/results unchanged.
        self.assertNotContains(response, 'href="?tag=tag-1#posts-list"')

    def test_category_filter(self):
        category = Category.objects.create(name="Guides", slug="guides", locale=self.catalog_index_page.locale)
        self.entry1.categories.add(category)
        self.entry1.save()

        response = self.client.get(self.catalog_index_page.url + "?category=guides")

        self.assertContains(response, "Entrée 1")
        self.assertNotContains(response, "Entrée 2")
        self.assertEqual(response.context["current_category"], category)
        self.assertContains(response, gettext("Filter by category"))
        self.assertEqual(response.context["extra_breadcrumbs"]["current"], "Guides")
        self.assertEqual(
            response.context["extra_title"], gettext("Pages in category %(category)s") % {"category": "Guides"}
        )
        # The category is shown as a chip on the card, not only in the filter sidebar.
        self.assertContains(response, '<p class="fr-tag">Guides</p>', html=True)

    def test_category_and_tag_filters_combine(self):
        category = Category.objects.create(name="Guides", slug="guides", locale=self.catalog_index_page.locale)
        self.entry1.categories.add(category)  # tag-1
        self.entry1.save()
        self.entry3.categories.add(category)  # tag-1 and tag-2
        self.entry3.save()

        response = self.client.get(self.catalog_index_page.url + "?category=guides&tag=tag-2")

        self.assertNotContains(response, "Entrée 1")
        self.assertContains(response, "Entrée 3")
        self.assertEqual(response.context["extra_breadcrumbs"]["current"], self.tag2)
        self.assertEqual(
            response.context["extra_title"],
            gettext("%(title)s, in category %(category)s")
            % {"title": gettext("Pages tagged with %(tag)s") % {"tag": "Tag 2"}, "category": "Guides"},
        )

    def make_category_tree(self, selection=CatalogIndexPage.MULTIPLE_FILTERS, operator=CatalogIndexPage.OR_OPERATOR):
        self.catalog_index_page.filter_selection = selection
        self.catalog_index_page.multiple_filter_operator = operator
        self.catalog_index_page.save()
        locale = self.catalog_index_page.locale
        self.regions = Category.objects.create(name="Régions", slug="regions", locale=locale)
        self.bretagne = Category.objects.create(name="Bretagne", slug="bretagne", parent=self.regions, locale=locale)
        self.finistere = Category.objects.create(
            name="Finistère", slug="finistere", parent=self.bretagne, locale=locale
        )
        self.alsace = Category.objects.create(name="Alsace", slug="alsace", parent=self.regions, locale=locale)
        Category.objects.create(name="Corse", slug="corse", parent=self.regions, locale=locale)  # unused
        self.sectors = Category.objects.create(name="Secteurs", slug="secteurs", locale=locale)
        self.btp = Category.objects.create(name="BTP", slug="btp", parent=self.sectors, locale=locale)
        self.entry1.categories.add(self.finistere, self.btp)
        self.entry1.save()
        self.entry2.categories.add(self.alsace)
        self.entry2.save()
        self.entry3.categories.add(self.btp)
        self.entry3.save()
        self.entry4.categories.add(self.bretagne)
        self.entry4.save()

    def get_entries(self, query=""):
        response = self.client.get(self.catalog_index_page.url + query)
        return response, sorted(entry.title for entry in response.context["entries"])

    @staticmethod
    def list_rows(response):
        return [
            (heading, [(chip.category, chip.checked) for chip in chips])
            for heading, chips in response.context["category_filters"].rows
        ]

    def test_each_root_category_in_use_is_a_group_of_its_subcategories(self):
        self.make_category_tree()

        response, entries = self.get_entries()

        self.assertEqual(
            self.list_rows(response),
            [
                (self.regions, [(self.bretagne, False), (self.alsace, False)]),  # Corse is unused
                (self.sectors, [(self.btp, False)]),
            ],
        )
        self.assertEqual(len(entries), 4)
        self.assertContains(response, '<h3 class="fr-h6">Régions</h3>', html=True)
        self.assertContains(response, 'id="category-bretagne"')
        # The group itself is a heading, not a filter.
        self.assertNotContains(response, 'id="category-regions"')

    def test_a_link_to_a_group_heading_filters_its_branch(self):
        self.make_category_tree()

        response, entries = self.get_entries("?category=regions")

        self.assertEqual(entries, ["Entrée 1", "Entrée 2", "Entrée 4"])
        self.assertEqual(response.context["current_categories"], [self.regions])

    def test_a_chosen_group_without_subcategories_in_use_is_left_out(self):
        self.make_category_tree()
        self.catalog_index_page.filter_categories.add(
            self.regions, Category.objects.create(name="Vide", slug="vide", locale=self.catalog_index_page.locale)
        )
        self.catalog_index_page.save()

        response, _ = self.get_entries()

        self.assertEqual([heading for heading, _ in self.list_rows(response)], [self.regions])

    def test_falls_back_to_every_category_when_no_chosen_group_has_anything_to_show(self):
        self.make_category_tree()
        # A subcategory chosen before only root categories could be groups.
        self.catalog_index_page.filter_categories.add(self.bretagne)
        self.catalog_index_page.save()

        response, _ = self.get_entries()

        self.assertEqual([heading for heading, _ in self.list_rows(response)], [self.regions, self.sectors])

    def test_or_operator_matches_any_ticked_category(self):
        self.make_category_tree()

        _, entries = self.get_entries("?category=bretagne&category=alsace")
        self.assertEqual(entries, ["Entrée 1", "Entrée 2", "Entrée 4"])

        _, entries = self.get_entries("?category=bretagne&category=btp")
        self.assertEqual(entries, ["Entrée 1", "Entrée 3", "Entrée 4"])

    def test_and_operator_matches_every_ticked_category(self):
        self.make_category_tree(operator=CatalogIndexPage.AND_OPERATOR)

        _, entries = self.get_entries("?category=bretagne&category=alsace")
        self.assertEqual(entries, [])

        response, entries = self.get_entries("?category=bretagne&category=btp")

        # Entrée 3 is in the BTP sector but in no region, Entrée 4 in Bretagne but in no sector.
        self.assertEqual(entries, ["Entrée 1"])
        self.assertEqual(response.context["current_categories"], [self.bretagne, self.btp])
        self.assertContains(response, 'id="category-bretagne"')  # checkboxes, as for the tags
        self.assertEqual(
            response.context["extra_title"],
            gettext("Pages in category %(category)s") % {"category": "Bretagne, BTP"},
        )

    def test_ticking_a_category_matches_its_branch_and_shows_its_subcategories(self):
        self.make_category_tree()

        response, entries = self.get_entries("?category=bretagne")

        self.assertEqual(entries, ["Entrée 1", "Entrée 4"])  # Entrée 1 is in Finistère
        self.assertEqual(
            self.list_rows(response),
            [
                (self.regions, [(self.bretagne, True), (self.alsace, False)]),
                (self.bretagne, [(self.finistere, False)]),
                (self.sectors, [(self.btp, False)]),
            ],
        )

    def test_a_ticked_subcategory_narrows_its_parent(self):
        self.make_category_tree()

        response, entries = self.get_entries("?category=bretagne&category=finistere")

        self.assertEqual(entries, ["Entrée 1"])
        self.assertEqual(response.context["current_category"], self.finistere)

    def test_a_link_to_a_subcategory_opens_its_branch(self):
        self.make_category_tree()

        response, entries = self.get_entries("?category=finistere")

        self.assertEqual(entries, ["Entrée 1"])
        self.assertEqual(self.list_rows(response)[1], (self.bretagne, [(self.finistere, True)]))

    def test_single_selection_keeps_one_category(self):
        self.make_category_tree(selection=CatalogIndexPage.SINGLE_FILTER)

        response, entries = self.get_entries("?category=bretagne&category=alsace")

        self.assertEqual(entries, ["Entrée 1", "Entrée 4"])
        self.assertEqual(response.context["current_categories"], [self.bretagne])
        # Links, as for the tags: one replaces the current category, the current one is removed.
        self.assertNotContains(response, 'id="category-bretagne"')
        self.assertContains(response, 'href="/catalog-index/?category=alsace#posts-list"')
        self.assertContains(response, 'href="/catalog-index/#posts-list"')

    def test_single_selection_still_narrows_down_the_tree(self):
        self.make_category_tree(selection=CatalogIndexPage.SINGLE_FILTER)

        response, entries = self.get_entries("?category=finistere")

        self.assertEqual(entries, ["Entrée 1"])
        self.assertEqual(self.list_rows(response)[1], (self.bretagne, [(self.finistere, True)]))
        # Clicking a ticked category, Bretagne included, clears the filter.
        self.assertContains(response, 'href="/catalog-index/#posts-list"', count=2)

    def test_preview_with_unsaved_category_groups(self):
        self.make_category_tree()
        # The preview renders the page from the edit form, unsaved: its groups are an in-memory relation.
        page = CatalogIndexPage.objects.get(pk=self.catalog_index_page.pk)
        page.filter_categories = [self.regions]
        request = self.client.get(self.catalog_index_page.url).wsgi_request

        response = page.make_preview_request(request, page.default_preview_mode)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([heading for heading, _ in page.category_filters().rows], [self.regions])

    def test_the_tag_form_keeps_the_ticked_categories(self):
        self.make_category_tree()

        response, _ = self.get_entries("?category=finistere&tag=tag-1")

        self.assertContains(response, '<input type="hidden" name="category" value="bretagne">', html=True)
        self.assertContains(response, '<input type="hidden" name="category" value="finistere">', html=True)
        self.assertContains(response, '<input type="hidden" name="tag" value="tag-1">', html=True)

    def test_chosen_categories_are_the_only_groups(self):
        self.make_category_tree()
        # Bretagne was chosen before only root categories could be: it is left out.
        self.catalog_index_page.filter_categories.add(self.regions, self.bretagne)
        self.catalog_index_page.save()

        response, entries = self.get_entries("?category=btp")  # not offered: ignored

        self.assertEqual(self.list_rows(response), [(self.regions, [(self.bretagne, False), (self.alsace, False)])])
        self.assertEqual(len(entries), 4)

    def test_sidebar_is_hidden_when_no_category_is_in_use(self):
        locale = self.catalog_index_page.locale
        theme = Category.objects.create(name="Thème", slug="theme", locale=locale)
        Category.objects.create(name="Guides", slug="guides", parent=theme, locale=locale)
        self.catalog_index_page.filter_categories.add(theme)
        self.catalog_index_page.filter_by_tag = False  # the fixture entries carry tags
        self.catalog_index_page.save()

        response = self.client.get(self.catalog_index_page.url)

        self.assertFalse(self.catalog_index_page.show_filters)
        self.assertNotContains(response, 'class="fr-sidemenu')

    def test_only_top_level_parent_categories_can_be_filter_groups(self):
        locale = self.catalog_index_page.locale
        theme = Category.objects.create(name="Thème", slug="theme", locale=locale)
        guides = Category.objects.create(name="Guides", slug="guides", parent=theme, locale=locale)
        Category.objects.create(name="Pratiques", slug="pratiques", parent=guides, locale=locale)
        Category.objects.create(name="Seule", slug="seule", locale=locale)

        form_class = CatalogIndexPage.get_edit_handler().get_form_class()
        form = form_class(instance=self.catalog_index_page, for_user=self.admin)

        self.assertEqual(list(form.fields["filter_categories"].queryset), [theme])

    def test_multiple_filter_and(self):
        self.catalog_index_page.filter_selection = CatalogIndexPage.MULTIPLE_FILTERS
        self.catalog_index_page.multiple_filter_operator = CatalogIndexPage.AND_OPERATOR
        self.catalog_index_page.save()

        url = self.catalog_index_page.url + "?tag=tag-1&tag=tag-2"
        response = self.client.get(url)

        self.assertNotContains(response, "Entrée 1")
        self.assertNotContains(response, "Entrée 2")
        self.assertContains(response, "Entrée 3")
        self.assertNotContains(response, "Entrée 4")

    def test_multiple_filter_or(self):
        self.catalog_index_page.filter_selection = CatalogIndexPage.MULTIPLE_FILTERS
        self.catalog_index_page.multiple_filter_operator = CatalogIndexPage.OR_OPERATOR
        self.catalog_index_page.save()

        url = self.catalog_index_page.url + "?tag=tag-1&tag=tag-2"
        response = self.client.get(url)

        self.assertContains(response, "Entrée 1")
        self.assertContains(response, "Entrée 2")
        self.assertContains(response, "Entrée 3")
        self.assertNotContains(response, "Entrée 4")

    def test_no_filter(self):
        url = self.catalog_index_page.url
        response = self.client.get(url)

        self.assertContains(response, "Entrée 1")
        self.assertContains(response, "Entrée 2")
        self.assertContains(response, "Entrée 3")
        self.assertContains(response, "Entrée 4")


class ErrorPagesTestCase(TestCase):
    def test_403_error_page(self):
        response = self.client.get("/403/")
        self.assertEqual(response.status_code, 403)
        self.assertInHTML(
            "<title>Erreur 403 — Accès refusé — Titre du site</title>",
            response.content.decode(),
        )
        self.assertNotContains(response, "fr-alert", status_code=403)

    def test_403_csrf_simulated_page(self):
        response = self.client.get("/403-csrf/")
        self.assertEqual(response.status_code, 403)
        self.assertInHTML(
            "<title>Erreur 403 — Accès refusé — Titre du site</title>",
            response.content.decode(),
        )
        self.assertContains(response, "fr-alert", status_code=403)
        self.assertContains(response, "Cause de l’erreur : CSRF cookie not set.", status_code=403)

    def test_403_on_real_csrf_failure(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post("/403/")
        self.assertEqual(response.status_code, 403)
        self.assertInHTML(
            "<title>Erreur 403 — Accès refusé — Titre du site</title>",
            response.content.decode(),
        )
        self.assertContains(response, "CSRF cookie not set.", status_code=403)

    def test_404_error_page(self):
        response = self.client.get("/404/")
        self.assertEqual(response.status_code, 404)
        self.assertInHTML(
            "<title>Erreur 404 — Page non trouvée — Titre du site</title>",
            response.content.decode(),
        )

    def test_500_error_page(self):
        response = self.client.get("/500/")
        self.assertEqual(response.status_code, 500)
        # Site settings are not available in a error 500 page so the site title is not there
        self.assertInHTML(
            "<title>Erreur 500 — Erreur inattendue</title>",
            response.content.decode(),
        )


class FollowBlockAriaLabelTestCase(WagtailPageTestCase):
    def setUp(self):
        home_page = Page.objects.get(slug="home")
        self.content_page = home_page.add_child(instance=ContentPage(title="Page de test", slug="follow-block-test"))
        self.config = CmsDsfrConfig.objects.get_or_create(site_id=home_page.get_site().id)[0]
        self.config.newsletter_description = ""
        self.config.newsletter_url = ""
        self.config.save()

    def _enable_newsletter(self):
        self.config.newsletter_description = "Description"
        self.config.newsletter_url = "https://example.com/newsletter"
        self.config.save()

    def _enable_social(self):
        self.config.social_media_items.create(title="Mastodon", url="https://example.com/mastodon")
        self.config.save()

    def _assert_aria_label(self, label):
        response = self.client.get(self.content_page.url)
        self.assertRegex(
            response.content.decode(),
            rf'<aside id="cmsfr-block-follow"\s+aria-label="{label}">',
        )

    def test_label_with_newsletter_and_social(self):
        self._enable_newsletter()
        self._enable_social()
        self._assert_aria_label("Lettre d’information et réseaux sociaux")

    def test_label_with_newsletter_only(self):
        self._enable_newsletter()
        self._assert_aria_label("Lettre d’information")

    def test_label_with_social_only(self):
        self._enable_social()
        self._assert_aria_label("Réseaux sociaux")

    def test_no_aside_when_block_is_empty(self):
        response = self.client.get(self.content_page.url)
        self.assertNotContains(response, "cmsfr-block-follow")
