from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.urls import reverse
from wagtail.images.models import Image
from wagtail.models import Page
from wagtail.rich_text import RichText

from content_manager.models import ContentPage
from content_manager.services.accessors import get_or_create_footer_bottom_menu, get_or_create_main_menu
from content_manager.utils import get_default_site
from forms.models import FormField, FormPage

ALL_ALLOWED_SLUGS = ["home", "mentions-legales", "accessibilite", "contact"]


class Command(BaseCommand):
    help = """
    Creates a series of starter pages, in order to avoid new sites having only a blank "Welcome to Wagtail" page.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug", nargs="+", type=str, help="[Optional] Slug of the page(s) to create", choices=ALL_ALLOWED_SLUGS
        )

    def handle(self, *args, **kwargs):
        call_command("import_dsfr_pictograms")
        call_command("import_illustration_images")

        slugs = kwargs.get("slug")

        if not slugs:
            # Only run the script on a new site or for specific slugs
            if Page.objects.last().id > 2:
                self.stdout.write(
                    self.style.WARNING(
                        "The site appears to already have pages, so this script won't run without params."
                    )
                )
                self.stdout.write(
                    self.style.WARNING("Please run this script on a new site, or with the 'slug' parameter.")
                )
                return
            else:
                # on a new site, first set the config
                call_command("set_config")

            slugs = ALL_ALLOWED_SLUGS

        for slug in slugs:
            if slug == "home":
                self.create_homepage()
            elif slug == "mentions-legales":
                title = "Mentions légales"
                body = []

                alert_block = {
                    "title": title,
                    "description": """Entrez ici les mentions légales du site.<br />
                    <a href="https://www.francenum.gouv.fr/guides-et-conseils/developpement-commercial/site-web/quelles-sont-les-mentions-legales-pour-un-site">
                    Que doivent-elles obligatoirement contenir ?</a>""",  # noqa
                    "level": "info",
                    "heading_tag": "h2",
                }
                body.append(("alert", alert_block))

                text_raw = """
                <p>D’après la <a href="https://www.systeme-de-design.gouv.fr/elements-d-interface/composants/pied-de-page">documentation du système de design</a>,
                le pied de page doit contenir a minima les quatre liens suivants :</p>
                <ul>
                    <li>Accessibilité : non/partiellement/totalement conforme</li>
                    <li>Mentions légales</li>
                    <li>Données personnelles</li>
                    <li>Gestion des cookies</li>
                </ul>
                <p>Ces deux derniers peuvent pointer vers des pages à part entière ou des sections de cette page.</p>
                """  # noqa
                body.append(("paragraph", RichText(text_raw)))

                self.create_page(slug=slug, title=title, body=body)
            elif slug == "accessibilite":
                title = "Déclaration d’accessibilité"
                body = []

                alert_block = {
                    "title": title,
                    "description": """Entrez ici la déclaration d’accessibilité.<br />
                    <a href="https://betagouv.github.io/a11y-generateur-declaration/#create">
                    Générateur de déclaration d’accessibilité</a>""",
                    "level": "info",
                    "heading_tag": "h2",
                }

                body.append(("alert", alert_block))
                self.create_page(slug=slug, title=title, body=body, footer_label="Accessibilité : non conforme")
            elif slug == "contact":
                self.create_contact_page(slug)
            else:
                raise ValueError(f"Valeur inconnue : {slug}")

    def create_homepage(self) -> None:
        """
        Create the homepage, set it as default and delete the initial page
        """
        # Don't replace a manually created home
        already_exists = ContentPage.objects.filter(slug="home").first()
        if already_exists:
            self.stdout.write(f"The home page seem to already exist with id {already_exists.id}")
            return

        # Create the page
        body = []
        title = "Votre nouveau site avec Sites Conformes"

        image = Image.objects.filter(title="Pictogrammes DSFR — Digital — Coding").first()
        # Mark the image as decorative for validations
        if image:
            image.is_decorative = True
            image.save()

        text_raw = """<p>Bienvenue !</p>

        <p>Vous venez de créer un site utilisant le gestionnaire de contenus de l’État.</p>

        <p>Vous pouvez maintenant vous connecter dans l’administration et personnaliser le site.</p>
        """

        # Use the reversed admin path directly to avoid duplicating the script_name
        admin_url = reverse("wagtailadmin_home")

        image_and_text_block = {
            "image": image,
            "image_ratio": "3",
            "text": RichText(text_raw),
            "link": {"external_url": admin_url, "text": "Gérer le site"},
        }

        body.append(("imageandtext", image_and_text_block))

        text_2_raw = """
        <p>En particulier, vous devrez :</p>
        <ul>
            <li>Configurer le site dans Configuration > Configuration du site</li>
            <li>Remplacer le contenu de la page de mentions légales</li>
            <li>Remplacer le contenu de cette page d’accueil.</li>
        </ul>
        """
        body.append(("paragraph", RichText(text_2_raw)))

        root = Page.objects.get(slug="root")
        home_page = root.add_child(instance=ContentPage(title=title, body=body, show_in_menus=True))

        # Define it as default for the default site
        site = get_default_site()

        site.root_page_id = home_page.id
        site.save()

        # Delete the original default page and get its slug
        original_home = Page.objects.get(slug="home")
        original_home.delete()

        home_page.slug = "home"
        home_page.save()

        self.stdout.write(self.style.SUCCESS(f"Homepage created with id {home_page.id}"))

    def create_page(self, slug: str, title: str, body: list, footer_label: str = ""):
        """
        Creates a page for the site and adds it to the footer
        """

        # Don't replace a manually created page
        already_exists = ContentPage.objects.filter(slug=slug).first()
        if already_exists:
            self.stdout.write(f"The {slug} page seem to already exist with id {already_exists.id}")
            return

        home_page = get_default_site().root_page
        new_page = home_page.add_child(instance=ContentPage(title=title, body=body, slug=slug, show_in_menus=True))

        footer_menu = get_or_create_footer_bottom_menu()

        link_label = footer_label if footer_label else title

        link_value = {
            "text": link_label,
            "page": new_page,
            "link_type": "page",
        }
        footer_menu.items.append(("link", link_value))

        self.stdout.write(self.style.SUCCESS(f"Page {slug} created with id {new_page.id}"))

    def create_contact_page(self, slug: str = "contact") -> None:
        """
        Creates a contact page for the site and adds it the main menu
        """

        # Don't replace a manually created page
        already_exists = ContentPage.objects.filter(slug=slug).first()
        if already_exists:
            self.stdout.write(f"The contact page seem to already exist with id {already_exists.id}")
            return

        # Create the form page
        title = "Contact"
        intro = RichText("""
            <p>Bonjour, n’hésitez pas à nous contacter via le formulaire ci-dessous.</p>
            <p></p>
            <p>Vous pouvez également nous contacter via &lt;autres méthodes&gt;.</p>
            <p></p>
            <p>Les champs marqués d’une astérisque (*) sont obligatoires.</p>""")

        thank_you_text = RichText("<p>Merci pour votre message ! Nous reviendrons vers vous rapidement.</p>")

        default_site = get_default_site()
        home_page = default_site.root_page
        contact_page = home_page.add_child(
            instance=FormPage(title=title, slug=slug, intro=intro, thank_you_text=thank_you_text, show_in_menus=True)
        )

        # Create the form fields
        fields = [
            {
                "sort_order": 0,
                "clean_name": "votre_nom_complet",
                "label": "Votre nom complet",
                "required": True,
                "page": contact_page,
                "field_type": "singleline",
            },
            {
                "sort_order": 1,
                "clean_name": "votre_adresse_electronique",
                "label": "Votre adresse électronique",
                "required": True,
                "choices": "",
                "default_value": "",
                "help_text": "Format attendu : nom@domaine.fr",
                "page": contact_page,
                "field_type": "email",
            },
            {
                "sort_order": 2,
                "clean_name": "votre_numero_de_telephone",
                "label": "Votre numéro de téléphone",
                "required": False,
                "page": contact_page,
                "field_type": "singleline",
            },
            {
                "sort_order": 3,
                "clean_name": "titre_de_votre_message",
                "label": "Titre de votre message",
                "required": True,
                "page": contact_page,
                "field_type": "singleline",
            },
            {
                "sort_order": 4,
                "clean_name": "votre_message",
                "label": "Votre message",
                "required": True,
                "choices": "",
                "default_value": "",
                "help_text": "",
                "page": contact_page,
                "field_type": "multiline",
            },
        ]

        for field_data in fields:
            FormField.objects.create(**field_data)

        # Menu item
        main_menu = get_or_create_main_menu()

        link_value = {
            "text": title,
            "page": contact_page,
            "link_type": "page",
        }
        main_menu.items.append(("link", link_value))
        main_menu.save()

        self.stdout.write(self.style.SUCCESS(f"Form page {slug} created with id {contact_page.id}"))
