from django.core.management.base import BaseCommand
from faker import Faker
from taggit.models import slugify
from wagtail.rich_text import RichText
from wagtailmenus.models.menuitems import FlatMenuItem, MainMenuItem
from wagtailmenus.models.menus import FlatMenu, MainMenu

from blog.models import BlogIndexPage
from content_manager.models import ContentPage, MegaMenu, MegaMenuCategory
from content_manager.services.accessors import get_or_create_catalog_index_page, get_or_create_content_page
from content_manager.utils import get_default_site
from forms.models import FormField, FormPage

ALL_ALLOWED_SLUGS = ["blog_index", "publications", "menu_page", "form"]

fake = Faker("fr_FR")


class Command(BaseCommand):
    help = """
    Creates a series of demo pages with a variety of content.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug", nargs="+", type=str, help="[Optional] Slug of the page(s) to create", choices=ALL_ALLOWED_SLUGS
        )

    def handle(self, *args, **kwargs):
        slugs = kwargs.get("slug")

        if not slugs:
            slugs = ALL_ALLOWED_SLUGS

        site = get_default_site()

        # First, add the home page to the main menu if not already done
        home_page = site.root_page
        locale = home_page.locale
        main_menu = MainMenu.objects.first()
        if not main_menu:
            main_menu = MainMenu.objects.create(site=site)
        MainMenuItem.objects.update_or_create(
            link_page=home_page, menu=main_menu, defaults={"link_text": "Accueil", "sort_order": 0}
        )

        for slug in slugs:
            if slug == "blog_index":
                blog_index = self.create_blog_index(home_page)
                MainMenuItem.objects.update_or_create(link_page=blog_index, menu=main_menu, defaults={"sort_order": 1})

                # to/do add example blog pages

            elif slug == "publications":
                self.create_publication_pages(site, main_menu)

            elif slug == "menu_page":
                # A blank page that is just destined to have a list of its subpages.
                body = [("subpageslist", None)]
                menu_page = get_or_create_content_page(slug, title="Pages d’exemple", body=body, parent_page=home_page)

                # Inserts it right before the last entry
                contact_menu_entry = MainMenuItem.objects.filter(menu=main_menu).last()
                MainMenuItem.objects.update_or_create(
                    link_page=menu_page, menu=main_menu, defaults={"sort_order": contact_menu_entry.sort_order}
                )
                contact_menu_entry.sort_order += 1  # type: ignore
                contact_menu_entry.save()

            elif slug == "form":
                menu_page = ContentPage.objects.get(slug="menu_page", locale=locale)
                self.create_form_page("form_with_all_fields", parent_page=menu_page)
            else:
                raise ValueError(f"Valeur inconnue : {slug}")

    def create_blog_index(self, home_page) -> BlogIndexPage:
        """
        Create the blog index
        """

        # Don't replace a manually created page
        already_exists = BlogIndexPage.objects.filter(slug="actualités").first()
        if already_exists:
            self.stdout.write(f"The page seem to already exist with id {already_exists.id}")
            return already_exists

        # Create the page
        body = []
        title = "Actualités"

        text_raw = """<p>Bienvenue !</p>

        <p>Vous trouverez ici nos dernières actualités</p>
        """

        body.append(("paragraph", RichText(text_raw)))

        blog_index = home_page.add_child(
            instance=BlogIndexPage(title=title, body=body, slug="actualités", show_in_menus=True)
        )

        self.stdout.write(self.style.SUCCESS(f"Blog index page created with id {blog_index.id}"))

        return blog_index

    def create_publication_pages(self, site, main_menu):
        slug = "publications"
        title = "Publications"
        body = []

        text_raw = """<p>Veuillez trouver ici une liste de publications</p>"""
        body.append(("paragraph", RichText(text_raw)))

        publications_page = get_or_create_catalog_index_page(slug=slug, title=title, body=body)
        publications_menu_item, _created = MainMenuItem.objects.update_or_create(
            link_page=publications_page, menu=main_menu, defaults={"sort_order": 2}
        )

        # Create the mega menu
        publications_mega_menu, _created = MegaMenu.objects.get_or_create(
            name="Méga-menu publications",
            parent_menu_item_id=publications_menu_item.id,
            description="Ceci est une description",
        )

        # Create a set of publications sub-pages
        for i in range(4):
            menu_category_menu, _created = FlatMenu.objects.get_or_create(
                site_id=site.id,
                title=f"Menu publications > Catégorie {i + 1}",
                handle=f"mega_menu_section_{i + 1}",
                heading=f"Colonne {i + 1}",
            )

            menu_category, _created = MegaMenuCategory.objects.get_or_create(
                mega_menu=publications_mega_menu, sort_order=i, category=menu_category_menu
            )

            for j in range(8):
                title = f"Page {i + 1} - {j + 1}"

                body = []
                text = ""
                for p in fake.paragraphs():
                    text += f"<p>{p}</p>\n"
                    body.append(("paragraph", RichText(text)))

                new_page = get_or_create_content_page(
                    slug=slugify(title), title=title, body=body, parent_page=publications_page
                )

                FlatMenuItem.objects.get_or_create(link_page=new_page, menu=menu_category_menu, sort_order=j)

            publications_mega_menu.categories.add(menu_category)
            publications_mega_menu.save()

    def create_form_page(self, slug: str, parent_page: ContentPage) -> None:
        """
        Creates a form page with all the different forms
        """

        # Don't replace a manually created page
        already_exists = FormPage.objects.filter(slug=slug).first()
        if already_exists:
            self.stdout.write(f"The page seem to already exist with id {already_exists.id}")
            return

        # Create the form page
        title = "Formulaire avec tous les champs"
        intro = RichText("<p>Texte d’introduction</p>")

        thank_you_text = RichText("<p>Merci pour votre message !</p>")

        form_page = parent_page.add_child(
            instance=FormPage(title=title, slug=slug, intro=intro, thank_you_text=thank_you_text, show_in_menus=True)
        )

        # Create the form fields
        fields = [
            {
                "sort_order": 0,
                "clean_name": "champ_texte",
                "label": "Champ texte",
                "required": True,
                "choices": "",
                "default_value": "",
                "help_text": "",
                "page": form_page,
                "field_type": "singleline",
            },
            {
                "sort_order": 1,
                "clean_name": "zone_de_texte",
                "label": "Zone de texte",
                "required": True,
                "page": form_page,
                "field_type": "multiline",
            },
            {
                "sort_order": 2,
                "clean_name": "adresse_email",
                "label": "Adresse email",
                "required": True,
                "page": form_page,
                "field_type": "email",
            },
            {
                "sort_order": 3,
                "clean_name": "nombre",
                "label": "Nombre",
                "default_value": 42,
                "required": True,
                "page": form_page,
                "field_type": "number",
            },
            {
                "sort_order": 4,
                "clean_name": "url",
                "label": "URL",
                "required": True,
                "page": form_page,
                "field_type": "url",
            },
            {
                "sort_order": 5,
                "clean_name": "case_a_cocher",
                "label": "Case à cocher",
                "required": True,
                "page": form_page,
                "field_type": "checkbox",
            },
            {
                "sort_order": 6,
                "clean_name": "cases_a_cocher",
                "label": "Cases à cocher",
                "required": True,
                "choices": "1\r\n2\r\n3",
                "default_value": "",
                "help_text": "",
                "page": form_page,
                "field_type": "checkboxes",
            },
            {
                "sort_order": 7,
                "clean_name": "liste_deroulante",
                "label": "Liste déroulante",
                "required": True,
                "choices": "4\r\n5\r\n6",
                "default_value": "",
                "help_text": "",
                "page": form_page,
                "field_type": "dropdown",
            },
            {
                "sort_order": 8,
                "clean_name": "boutons_radio",
                "label": "Boutons radio",
                "required": True,
                "choices": "7\r\n8\r\n9",
                "default_value": "",
                "help_text": "",
                "page": form_page,
                "field_type": "radio",
            },
            {
                "sort_order": 9,
                "clean_name": "date",
                "label": "Date",
                "required": True,
                "choices": "",
                "default_value": "",
                "help_text": "",
                "page": form_page,
                "field_type": "date",
            },
            {
                "sort_order": 10,
                "clean_name": "champ_cache",
                "label": "Champ caché",
                "required": True,
                "choices": "",
                "default_value": "valeur",
                "help_text": "",
                "page": form_page,
                "field_type": "hidden",
            },
        ]

        for field_data in fields:
            FormField.objects.create(**field_data)

        self.stdout.write(self.style.SUCCESS(f"Page {slug} created with id {form_page.id}"))
