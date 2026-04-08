import os

from django.conf import settings
from django.core.management.base import BaseCommand
from faker import Faker
from taggit.models import slugify
from wagtail.images import get_image_model
from wagtail.rich_text import RichText

from blog.models import BlogIndexPage
from content_manager.models import ContentPage
from content_manager.services.accessors import (
    get_or_create_catalog_index_page,
    get_or_create_content_page,
    get_or_create_main_menu,
)
from content_manager.utils import get_default_site, import_image
from forms.models import FormField, FormPage

ALL_ALLOWED_SLUGS = ["blog_index", "publications", "menu_page", "form", "common_blocks", "hero_blocks"]

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
        main_menu = get_or_create_main_menu()

        for slug in slugs:
            if slug == "blog_index":
                blog_index = self.create_blog_index(home_page)

                link_value = {
                    "text": blog_index.title,
                    "page": blog_index,
                    "link_type": "page",
                }
                main_menu.items.append(("link", link_value))

                # to/do add example blog pages

            elif slug == "publications":
                self.create_publication_pages(site, main_menu)

            elif slug == "menu_page":
                # A blank page that is just destined to have a list of its subpages.
                body = [("subpageslist", None)]
                menu_page = get_or_create_content_page(slug, title="Pages d'exemple", body=body, parent_page=home_page)

                # Inserts it right before the last entry

                link_value = {
                    "text": menu_page.title,
                    "page": menu_page,
                    "link_type": "page",
                }
                main_menu.items.insert(-1, ("link", link_value))

            elif slug == "form":
                menu_page = ContentPage.objects.get(slug="menu_page", locale=locale)
                self.create_form_page("form_with_all_fields", parent_page=menu_page)

            elif slug == "common_blocks":
                menu_page = ContentPage.objects.get(slug="menu_page", locale=locale)
                self.create_common_blocks_page(parent_page=menu_page)

            elif slug == "hero_blocks":
                menu_page = ContentPage.objects.get(slug="menu_page", locale=locale)
                self.create_hero_blocks_page(home_page=home_page, parent_page=menu_page)

            else:
                raise ValueError(f"Valeur inconnue : {slug}")

        main_menu.save()

    def get_or_import_image(self, path: str, title: str):
        """Get an existing image by title or import it from the given path."""
        Image = get_image_model()
        image = Image.objects.filter(title=title).first()
        if not image:
            full_path = os.path.join(settings.BASE_DIR, path)
            image = import_image(full_path, title)
        return image

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

        text_raw = """<p>Bienvenue !</p>

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

        menu_columns = []

        # Create a set of publications sub-pages
        for i in range(4):
            menu_column_value = {
                "label": f"Colonne {i + 1}",
                "links": [],
            }

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

                menu_column_value["links"].append(("link", {"text": title, "page": new_page, "link_type": "page"}))

            menu_column = ("column", menu_column_value)

            menu_columns.append(menu_column)

        mega_menu_values = {
            "label": "Publications",
            "columns": menu_columns,
            "description": "Découvrez nos publications",
            "main_link": {"text": publications_page.title, "page": publications_page, "link_type": "page"},
        }
        main_menu.items.insert(-1, ("megamenu", mega_menu_values))
        main_menu.save()

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
        intro = RichText("<p>Texte d'introduction</p>")

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

    def create_common_blocks_page(self, parent_page: ContentPage) -> None:
        """
        Creates a page showcasing all blocks in STREAMFIELD_COMMON_BLOCKS.
        """
        slug = "common_blocks"

        already_exists = ContentPage.objects.filter(slug=slug).first()
        if already_exists:
            self.stdout.write(f"The page seem to already exist with id {already_exists.id}")
            return

        # Load images
        img_banner = self.get_or_import_image(
            "static/illustration/Banner-Sites-Faciles-Dimitri-Iakymuk-unsplash.jpg",
            "Banner Sites Faciles Dimitri Iakymuk Unsplash",
        )
        img_femme = self.get_or_import_image(
            "static/illustration/illustration-sites-faciles-femme-ordinateur.png",
            "Illustration Sites Faciles Femme Ordinateur",
        )
        img_homme = self.get_or_import_image(
            "static/illustration/illustration-sites-faciles-homme-nuages.png",
            "Illustration Sites Faciles Homme Nuages",
        )
        img_placeholder = self.get_or_import_image(
            "static/illustration/Placeholder-Sites-Faciles.png",
            "Placeholder Sites Faciles",
        )
        img_error = self.get_or_import_image(
            "static/artwork/technical-error.svg",
            "Technical Error",
        )

        body = []

        # paragraph
        text = "".join(f"<p>{p}</p>" for p in fake.paragraphs(nb=3))
        body.append(("paragraph", RichText(text)))

        # image (CenteredImageBlock - ImageChooserBlock)
        body.append(
            (
                "image",
                {
                    "title": fake.sentence(nb_words=4),
                    "heading_tag": "h3",
                    "image": img_femme,
                    "alt": "Une femme devant un ordinateur",
                    "caption": fake.sentence(nb_words=6),
                    "width": "",
                    "image_ratio": "",
                    "url": "",
                },
            )
        )

        # imageandtext (ImageAndTextBlock - ImageBlock)
        body.append(
            (
                "imageandtext",
                {
                    "image": {"image": img_homme, "alt_text": "Un homme dans les nuages", "decorative": False},
                    "image_side": "right",
                    "image_ratio": "3",
                    "text": RichText(f"<p>{fake.paragraph()}</p>"),
                    "link": {
                        "link_type": "external_url",
                        "external_url": fake.url(),
                        "page": None,
                        "document": None,
                        "anchor": "",
                        "text": "En savoir plus",
                    },
                },
            )
        )

        # table (AdvancedTypedTableBlock / TypedTableBlock)
        body.append(
            (
                "table",
                {
                    "caption": fake.sentence(nb_words=5),
                    "columns": [
                        {"type": "text", "heading": "Nom"},
                        {"type": "text", "heading": "Rôle"},
                        {"type": "text", "heading": "Ville"},
                    ],
                    "rows": [
                        {"values": [fake.name(), fake.job(), fake.city()]},
                        {"values": [fake.name(), fake.job(), fake.city()]},
                        {"values": [fake.name(), fake.job(), fake.city()]},
                    ],
                },
            )
        )

        # alert
        body.append(
            (
                "alert",
                {
                    "title": fake.sentence(nb_words=5),
                    "description": fake.paragraph(),
                    "level": "info",
                    "heading_tag": "h3",
                },
            )
        )

        # text_cta
        body.append(
            (
                "text_cta",
                {
                    "text": RichText(f"<p>{fake.paragraph()}</p>"),
                    "cta_buttons": [
                        (
                            "buttons",
                            [
                                (
                                    "button",
                                    {
                                        "text": "Appel à l'action",
                                        "button_type": "fr-btn",
                                        "link_type": "external_url",
                                        "external_url": fake.url(),
                                        "page": None,
                                        "document": None,
                                        "anchor": "",
                                        "icon_class": "",
                                        "icon_side": "",
                                    },
                                )
                            ],
                        )
                    ],
                },
            )
        )

        # video
        body.append(
            (
                "video",
                {
                    "title": "Vidéo de démonstration",
                    "caption": fake.sentence(nb_words=5),
                    "url": "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
                    "width": "",
                    "video_ratio": "h3",
                    "transcription": {
                        "title": "Transcription",
                        "content": RichText(f"<p>{fake.paragraph()}</p>"),
                    },
                },
            )
        )

        # transcription
        body.append(
            (
                "transcription",
                {
                    "title": "Transcription",
                    "content": RichText(f"<p>{fake.paragraph()}</p>"),
                },
            )
        )

        # badges_list (StreamBlock)
        body.append(
            (
                "badges_list",
                [
                    ("badge", {"text": "Nouveau", "color": "new", "hide_icon": False}),
                    ("badge", {"text": "Succès", "color": "success", "hide_icon": False}),
                    ("badge", {"text": "Erreur", "color": "error", "hide_icon": False}),
                ],
            )
        )

        # tags_list (StreamBlock)
        body.append(
            (
                "tags_list",
                [
                    (
                        "tag",
                        {
                            "label": "Science",
                            "is_small": False,
                            "color": "",
                            "icon_class": "",
                            "link": {
                                "link_type": "",
                                "page": None,
                                "document": None,
                                "external_url": "",
                                "anchor": "",
                            },
                        },
                    ),
                    (
                        "tag",
                        {
                            "label": "Numérique",
                            "is_small": False,
                            "color": "",
                            "icon_class": "",
                            "link": {
                                "link_type": "",
                                "page": None,
                                "document": None,
                                "external_url": "",
                                "anchor": "",
                            },
                        },
                    ),
                    (
                        "tag",
                        {
                            "label": "Innovation",
                            "is_small": False,
                            "color": "",
                            "icon_class": "",
                            "link": {
                                "link_type": "",
                                "page": None,
                                "document": None,
                                "external_url": "",
                                "anchor": "",
                            },
                        },
                    ),
                ],
            )
        )

        # buttons_list
        body.append(
            (
                "buttons_list",
                {
                    "buttons": [
                        (
                            "button",
                            {
                                "text": "Bouton primaire",
                                "button_type": "fr-btn",
                                "link_type": "external_url",
                                "external_url": fake.url(),
                                "page": None,
                                "document": None,
                                "anchor": "",
                                "icon_class": "",
                                "icon_side": "",
                            },
                        ),
                        (
                            "button",
                            {
                                "text": "Bouton secondaire",
                                "button_type": "fr-btn fr-btn--secondary",
                                "link_type": "external_url",
                                "external_url": fake.url(),
                                "page": None,
                                "document": None,
                                "anchor": "",
                                "icon_class": "",
                                "icon_side": "",
                            },
                        ),
                    ],
                    "position": "",
                },
            )
        )

        # link (SingleLinkBlock)
        body.append(
            (
                "link",
                {
                    "link_type": "external_url",
                    "external_url": fake.url(),
                    "page": None,
                    "document": None,
                    "anchor": "",
                    "text": "Lien de démonstration",
                    "icon": "",
                    "size": "",
                },
            )
        )

        # accordions (AccordionsBlock - StreamBlock)
        body.append(
            (
                "accordions",
                [
                    ("title", "Titre des accordéons"),
                    (
                        "accordion",
                        {"title": fake.sentence(nb_words=5), "content": RichText(f"<p>{fake.paragraph()}</p>")},
                    ),
                    (
                        "accordion",
                        {"title": fake.sentence(nb_words=5), "content": RichText(f"<p>{fake.paragraph()}</p>")},
                    ),
                    (
                        "accordion",
                        {"title": fake.sentence(nb_words=5), "content": RichText(f"<p>{fake.paragraph()}</p>")},
                    ),
                ],
            )
        )

        # callout
        body.append(
            (
                "callout",
                {
                    "title": fake.sentence(nb_words=4),
                    "heading_tag": "h3",
                    "icon_class": "",
                    "text": RichText(f"<p>{fake.paragraph()}</p>"),
                    "color": "blue-cumulus",
                },
            )
        )

        # highlight
        body.append(
            (
                "highlight",
                {
                    "text": RichText(f"<p>{fake.paragraph()}</p>"),
                    "color": "yellow-tournesol",
                    "size": "",
                },
            )
        )

        # quote
        body.append(
            (
                "quote",
                {
                    "image": img_placeholder,
                    "quote": fake.sentence(nb_words=10),
                    "author_name": fake.name(),
                    "author_title": fake.job(),
                    "color": "blue-cumulus",
                },
            )
        )

        # stepper
        steps_data = [
            ("step", {"title": fake.sentence(nb_words=3), "detail": fake.sentence(nb_words=6)}),
            ("step", {"title": fake.sentence(nb_words=3), "detail": fake.sentence(nb_words=6)}),
            ("step", {"title": fake.sentence(nb_words=3), "detail": fake.sentence(nb_words=6)}),
            ("step", {"title": fake.sentence(nb_words=3), "detail": fake.sentence(nb_words=6)}),
        ]
        body.append(
            (
                "stepper",
                {
                    "title": "Processus en étapes",
                    "total": 4,
                    "current": 2,
                    "steps": steps_data,
                },
            )
        )

        # card (HorizontalCardBlock - ImageBlock)
        body.append(
            (
                "card",
                {
                    "title": fake.sentence(nb_words=5),
                    "heading_tag": "h3",
                    "description": RichText(f"<p>{fake.paragraph()}</p>"),
                    "image": {"image": img_banner, "alt_text": "Image de la carte", "decorative": False},
                    "image_ratio": "h3",
                    "image_badge": [],
                    "link": {
                        "link_type": "external_url",
                        "external_url": fake.url(),
                        "page": None,
                        "document": None,
                        "anchor": "",
                    },
                    "top_detail_text": fake.date(),
                    "top_detail_icon": "",
                    "top_detail_badges_tags": [],
                    "bottom_detail_text": "",
                    "bottom_detail_icon": "",
                    "call_to_action": [],
                    "grey_background": False,
                    "no_background": False,
                    "no_border": False,
                    "shadow": False,
                },
            )
        )

        # tile (TileBlock - ImageChooserBlock)
        body.append(
            (
                "tile",
                {
                    "title": fake.sentence(nb_words=4),
                    "heading_tag": "h3",
                    "description": RichText(f"<p>{fake.sentence()}</p>"),
                    "image": img_error,
                    "link": {
                        "link_type": "external_url",
                        "external_url": fake.url(),
                        "page": None,
                        "document": None,
                        "anchor": "",
                    },
                    "top_detail_badges_tags": [],
                    "detail_text": "",
                    "is_small": False,
                    "grey_background": False,
                    "no_background": False,
                    "no_border": False,
                    "shadow": False,
                    "is_horizontal": False,
                },
            )
        )

        # tabs (TabsBlock - StreamBlock)
        body.append(
            (
                "tabs",
                [
                    ("tabs", {"title": "Onglet 1", "content": [("text", RichText(f"<p>{fake.paragraph()}</p>"))]}),
                    ("tabs", {"title": "Onglet 2", "content": [("text", RichText(f"<p>{fake.paragraph()}</p>"))]}),
                    ("tabs", {"title": "Onglet 3", "content": [("text", RichText(f"<p>{fake.paragraph()}</p>"))]}),
                ],
            )
        )

        # markdown
        body.append(
            (
                "markdown",
                f"## {fake.sentence(nb_words=4)}\n\n{fake.paragraph()}\n\n"
                f"### {fake.sentence(nb_words=3)}\n\n{fake.paragraph()}",
            )
        )

        # iframe
        body.append(
            (
                "iframe",
                {
                    "title": "Données ouvertes",
                    "url": "https://data.gouv.fr/",
                    "height": 400,
                    "parameters": "",
                },
            )
        )

        # html
        body.append(
            (
                "html",
                f'<div class="fr-p-2w fr-background-alt--grey"><p>{fake.paragraph()}</p></div>',
            )
        )

        # anchor
        body.append(
            (
                "anchor",
                {"anchor_id": "section-demo"},
            )
        )

        # separator
        body.append(
            (
                "separator",
                {"top_margin": 3, "bottom_margin": 3},
            )
        )

        # multicolumns
        body.append(
            (
                "multicolumns",
                {
                    "bg_image": None,
                    "bg_color_class": "",
                    "title": fake.sentence(nb_words=4),
                    "heading_tag": "h2",
                    "top_margin": 5,
                    "bottom_margin": 5,
                    "vertical_align": "",
                    "columns": [
                        ("text", RichText(f"<p>{fake.paragraph()}</p>")),
                        ("text", RichText(f"<p>{fake.paragraph()}</p>")),
                    ],
                },
            )
        )

        # item_grid
        body.append(
            (
                "item_grid",
                {
                    "column_width": "4",
                    "horizontal_align": "left",
                    "vertical_align": "",
                    "items": [
                        (
                            "tile",
                            {
                                "title": fake.sentence(nb_words=3),
                                "heading_tag": "h3",
                                "description": RichText(f"<p>{fake.sentence()}</p>"),
                                "image": img_error,
                                "link": {
                                    "link_type": "external_url",
                                    "external_url": fake.url(),
                                    "page": None,
                                    "document": None,
                                    "anchor": "",
                                },
                                "top_detail_badges_tags": [],
                                "detail_text": "",
                                "is_small": False,
                                "grey_background": False,
                                "no_background": False,
                                "no_border": False,
                                "shadow": False,
                                "is_horizontal": False,
                            },
                        ),
                        (
                            "tile",
                            {
                                "title": fake.sentence(nb_words=3),
                                "heading_tag": "h3",
                                "description": RichText(f"<p>{fake.sentence()}</p>"),
                                "image": img_error,
                                "link": {
                                    "link_type": "external_url",
                                    "external_url": fake.url(),
                                    "page": None,
                                    "document": None,
                                    "anchor": "",
                                },
                                "top_detail_badges_tags": [],
                                "detail_text": "",
                                "is_small": False,
                                "grey_background": False,
                                "no_background": False,
                                "no_border": False,
                                "shadow": False,
                                "is_horizontal": False,
                            },
                        ),
                    ],
                },
            )
        )

        # fullwidthbackground
        body.append(
            (
                "fullwidthbackground",
                {
                    "bg_image": None,
                    "bg_color_class": "blue-france",
                    "top_margin": 5,
                    "bottom_margin": 5,
                    "content": [
                        ("text", RichText(f"<p>{fake.paragraph()}</p>")),
                    ],
                },
            )
        )

        # fullwidthbackgroundwithsidemenu
        body.append(
            (
                "fullwidthbackgroundwithsidemenu",
                {
                    "bg_image": None,
                    "bg_color_class": "",
                    "top_margin": 5,
                    "bottom_margin": 5,
                    "main_content": [
                        ("text", RichText(f"<h2>{fake.sentence(nb_words=4)}</h2><p>{fake.paragraph()}</p>")),
                    ],
                    "sidemenu_title": "Menu latéral",
                    "sidemenu_content": [
                        ("html", "<ul><li><a href='#section-demo'>Section démo</a></li></ul>"),
                    ],
                },
            )
        )

        # subpageslist
        body.append(("subpageslist", None))

        # blog_recent_entries and events_recent_entries require existing blog/events index pages,
        # so they are omitted here. Add them manually via the admin once a blog index exists.

        # layout_richtext (ResizedTextSection)
        body.append(
            (
                "layout_richtext",
                {
                    "text": RichText(f"<h2>{fake.sentence(nb_words=4)}</h2><p>{fake.paragraph()}</p>"),
                    "width": "8",
                    "alignment": "",
                },
            )
        )

        # image_text_grid_section (ImageAndTextGridSection)
        body.append(
            (
                "image_text_grid_section",
                {
                    "section_title": fake.sentence(nb_words=4),
                    "layout": {"top_margin": 5, "bottom_margin": 5, "background_color": ""},
                    "items_alignement": "left",
                    "items_per_row": "4",
                    "images_size": "80",
                    "items": [
                        {
                            "image": {"image": img_error, "alt_text": "", "decorative": True},
                            "title": fake.sentence(nb_words=3),
                            "text": RichText(f"<p>{fake.sentence()}</p>"),
                        },
                        {
                            "image": {"image": img_error, "alt_text": "", "decorative": True},
                            "title": fake.sentence(nb_words=3),
                            "text": RichText(f"<p>{fake.sentence()}</p>"),
                        },
                        {
                            "image": {"image": img_error, "alt_text": "", "decorative": True},
                            "title": fake.sentence(nb_words=3),
                            "text": RichText(f"<p>{fake.sentence()}</p>"),
                        },
                    ],
                },
            )
        )

        # image_text_cta_section (ImageTextCTASection)
        body.append(
            (
                "image_text_cta_section",
                {
                    "text": RichText(f"<h2>{fake.sentence(nb_words=4)}</h2><p>{fake.paragraph()}</p>"),
                    "position": "left",
                    "button": {
                        "text": "En savoir plus",
                        "button_type": "fr-btn fr-btn--secondary",
                        "link_type": "external_url",
                        "external_url": fake.url(),
                        "page": None,
                        "document": None,
                        "anchor": "",
                        "icon_class": "",
                        "icon_side": "--",
                    },
                    "image": {"image": img_femme, "alt_text": "", "decorative": True},
                    "layout": {"top_margin": 5, "bottom_margin": 5, "background_color": ""},
                },
            )
        )

        # cta_section (CTASection)
        body.append(
            (
                "cta_section",
                {
                    "section_title": fake.sentence(nb_words=4),
                    "layout": {"top_margin": 5, "bottom_margin": 5, "background_color": ""},
                    "text": RichText(f"<p>{fake.paragraph()}</p>"),
                    "button": {
                        "text": "Appel à l'action",
                        "button_type": "fr-btn",
                        "link_type": "external_url",
                        "external_url": fake.url(),
                        "page": None,
                        "document": None,
                        "anchor": "",
                        "icon_class": "",
                        "icon_side": "--",
                    },
                },
            )
        )

        # spotlight_section (SpotlightSection)
        card_data = {
            "title": fake.sentence(nb_words=4),
            "heading_tag": "h3",
            "description": RichText(f"<p>{fake.paragraph()}</p>"),
            "image": {"image": img_placeholder, "alt_text": "", "decorative": True},
            "image_ratio": "h3",
            "image_badge": [],
            "link": {
                "link_type": "--",
                "page": None,
                "external_url": "",
                "document": None,
                "anchor": "",
            },
            "top_detail_text": "",
            "top_detail_icon": "",
            "top_detail_badges_tags": [],
            "bottom_detail_text": "",
            "bottom_detail_icon": "",
            "call_to_action": [],
            "grey_background": False,
            "no_background": False,
            "no_border": False,
            "shadow": False,
        }
        body.append(
            (
                "spotlight_section",
                {
                    "section_title": fake.sentence(nb_words=4),
                    "layout": {"top_margin": 5, "bottom_margin": 5, "background_color": ""},
                    "items_per_row": "4",
                    "link": {
                        "link_type": "",
                        "page": None,
                        "document": None,
                        "external_url": "",
                        "anchor": "",
                        "text": "",
                    },
                    "items": [
                        ("card", card_data),
                        ("card", card_data),
                        ("card", card_data),
                    ],
                },
            )
        )

        # accordion_section (AccordionSection)
        body.append(
            (
                "accordion_section",
                {
                    "accordion": [
                        ("title", "Accordéons"),
                        (
                            "accordion",
                            {"title": fake.sentence(nb_words=5), "content": RichText(f"<p>{fake.paragraph()}</p>")},
                        ),
                        (
                            "accordion",
                            {"title": fake.sentence(nb_words=5), "content": RichText(f"<p>{fake.paragraph()}</p>")},
                        ),
                    ],
                    "layout": {"top_margin": 5, "bottom_margin": 5, "background_color": ""},
                },
            )
        )

        page = get_or_create_content_page(slug, title="Tous les blocs", body=body, parent_page=parent_page)
        self.stdout.write(self.style.SUCCESS(f"Page {slug} created with id {page.id}"))

    def create_hero_blocks_page(self, home_page, parent_page: ContentPage) -> None:
        """
        Creates a parent hero_blocks page plus sub-pages for each hero type.
        """
        slug = "hero_blocks"

        # Load images
        img_banner = self.get_or_import_image(
            "static/illustration/Banner-Sites-Faciles-Dimitri-Iakymuk-unsplash.jpg",
            "Banner Sites Faciles Dimitri Iakymuk Unsplash",
        )
        img_homme = self.get_or_import_image(
            "static/illustration/illustration-sites-faciles-homme-nuages.png",
            "Illustration Sites Faciles Homme Nuages",
        )

        # Create the parent hero_blocks index page
        hero_blocks_page = get_or_create_content_page(
            slug,
            title="Blocs hero",
            body=[("subpageslist", None)],
            parent_page=parent_page,
        )

        # Hero type 1: hero_text_image
        hero_text_image_slug = "hero-text-image"
        if not ContentPage.objects.filter(slug=hero_text_image_slug).exists():
            hero_text_image_page = hero_blocks_page.add_child(
                instance=ContentPage(
                    title="Hero - Image et texte",
                    slug=hero_text_image_slug,
                    show_in_menus=True,
                    hero=[
                        (
                            "hero_text_image",
                            {
                                "text_content": {
                                    "hero_title": fake.sentence(nb_words=5),
                                    "hero_subtitle": RichText(f"<p>{fake.paragraph()}</p>"),
                                    "position": "left",
                                },
                                "buttons": [
                                    {
                                        "text": "Découvrir",
                                        "button_type": "fr-btn",
                                        "link_type": "external_url",
                                        "external_url": fake.url(),
                                        "page": None,
                                        "document": None,
                                        "anchor": "",
                                        "icon_class": "",
                                        "icon_side": "",
                                    }
                                ],
                                "image": {
                                    "image": img_homme,
                                    "alt_text": "Illustration",
                                    "decorative": False,
                                },
                                "layout": {
                                    "top_margin": 5,
                                    "bottom_margin": 5,
                                    "background_color": "",
                                },
                            },
                        )
                    ],
                    body=[],
                )
            )
            self.stdout.write(
                self.style.SUCCESS(f"Page {hero_text_image_slug} created with id {hero_text_image_page.id}")
            )
        else:
            self.stdout.write(f"Page {hero_text_image_slug} already exists")

        # Hero type 2: hero_text_wide_image
        hero_text_wide_image_slug = "hero-text-wide-image"
        if not ContentPage.objects.filter(slug=hero_text_wide_image_slug).exists():
            hero_text_wide_image_page = hero_blocks_page.add_child(
                instance=ContentPage(
                    title="Hero - Bannière large",
                    slug=hero_text_wide_image_slug,
                    show_in_menus=True,
                    hero=[
                        (
                            "hero_text_wide_image",
                            {
                                "text_content": {
                                    "hero_title": fake.sentence(nb_words=5),
                                    "hero_subtitle": RichText(f"<p>{fake.paragraph()}</p>"),
                                    "position": "center",
                                },
                                "layout": {
                                    "top_margin": 5,
                                    "bottom_margin": 5,
                                    "background_color": "",
                                },
                                "buttons": [
                                    {
                                        "text": "En savoir plus",
                                        "button_type": "fr-btn",
                                        "link_type": "external_url",
                                        "external_url": fake.url(),
                                        "page": None,
                                        "document": None,
                                        "anchor": "",
                                        "icon_class": "",
                                        "icon_side": "",
                                    }
                                ],
                                "image": {
                                    "image": {"image": img_banner, "alt_text": "Bannière", "decorative": False},
                                    "image_positioning": "bottom",
                                    "image_width": "fr-content-media--lg",
                                    "image_ratio": "fr-ratio-32x9",
                                },
                            },
                        )
                    ],
                    body=[],
                )
            )
            self.stdout.write(
                self.style.SUCCESS(f"Page {hero_text_wide_image_slug} created with id {hero_text_wide_image_page.id}")
            )
        else:
            self.stdout.write(f"Page {hero_text_wide_image_slug} already exists")

        # Hero type 3: hero_text_background_image
        hero_bg_slug = "hero-text-background-image"
        if not ContentPage.objects.filter(slug=hero_bg_slug).exists():
            hero_bg_page = hero_blocks_page.add_child(
                instance=ContentPage(
                    title="Hero - Image de fond",
                    slug=hero_bg_slug,
                    show_in_menus=True,
                    hero=[
                        (
                            "hero_text_background_image",
                            {
                                "text_content": {
                                    "hero_title": fake.sentence(nb_words=5),
                                    "hero_subtitle": RichText(f"<p>{fake.paragraph()}</p>"),
                                    "position": "",
                                },
                                "buttons": [
                                    {
                                        "text": "Commencer",
                                        "button_type": "fr-btn",
                                        "link_type": "external_url",
                                        "external_url": fake.url(),
                                        "page": None,
                                        "document": None,
                                        "anchor": "",
                                        "icon_class": "",
                                        "icon_side": "",
                                    }
                                ],
                                "background_color_or_image": "image",
                                "image": {
                                    "image": {"image": img_banner, "alt_text": "Image de fond", "decorative": False},
                                    "image_positioning": "",
                                    "image_mask": "darken",
                                },
                                "background_color": None,
                            },
                        )
                    ],
                    body=[],
                )
            )
            self.stdout.write(self.style.SUCCESS(f"Page {hero_bg_slug} created with id {hero_bg_page.id}"))
        else:
            self.stdout.write(f"Page {hero_bg_slug} already exists")

        # Hero type 4: old_hero
        hero_old_slug = "hero-old"
        if not ContentPage.objects.filter(slug=hero_old_slug).exists():
            hero_old_page = hero_blocks_page.add_child(
                instance=ContentPage(
                    title="Hero - Configurable (ancien)",
                    slug=hero_old_slug,
                    show_in_menus=True,
                    hero=[
                        (
                            "old_hero",
                            {
                                "header_with_title": True,
                                "header_image": {"image": img_banner, "alt_text": "", "decorative": True},
                                "header_color_class": "",
                                "header_large": False,
                                "header_darken": True,
                                "header_cta_text": RichText(f"<p>{fake.paragraph()}</p>"),
                                "header_cta_buttons": [
                                    (
                                        "button",
                                        {
                                            "text": "Action principale",
                                            "button_type": "fr-btn",
                                            "link_type": "external_url",
                                            "external_url": fake.url(),
                                            "page": None,
                                            "document": None,
                                            "anchor": "",
                                            "icon_class": "",
                                            "icon_side": "",
                                        },
                                    )
                                ],
                            },
                        )
                    ],
                    body=[],
                )
            )
            self.stdout.write(self.style.SUCCESS(f"Page {hero_old_slug} created with id {hero_old_page.id}"))
        else:
            self.stdout.write(f"Page {hero_old_slug} already exists")
