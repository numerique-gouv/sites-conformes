import swapper
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse
from wagtail.models import Page, Site
from wagtail.rich_text import RichText

from sites_conformes.core.services.accessors import get_or_create_footer_bottom_menu, get_or_create_main_menu
from sites_conformes.core.services.sites import import_installed_images
from sites_conformes.core.utils import get_default_site, get_installed_image
from sites_conformes.forms.models import FormField, FormPage

ContentPage = swapper.load_model("sites_conformes_core", "ContentPage")

ALL_ALLOWED_SLUGS = ["home", "mentions-legales", "accessibilite", "contact"]

# Pages created for a given site: its home page already exists
SITE_SLUGS = ["mentions-legales", "accessibilite", "contact"]


class Command(BaseCommand):
    help = """
    Creates a series of starter pages, in order to avoid new sites having only a blank "Welcome to Wagtail" page.

    With --site, creates the pages below the home page of this site, even if the instance already has pages.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug", nargs="+", type=str, help="[Optional] Slug of the page(s) to create", choices=ALL_ALLOWED_SLUGS
        )
        parser.add_argument(
            "--site",
            type=int,
            help="[Optional] ID of the site to create the pages in. Defaults to the default site.",
        )

    def handle(self, *args, **kwargs):
        site_id = kwargs.get("site")
        slugs = kwargs.get("slug")

        if site_id is not None:
            site = Site.objects.filter(pk=site_id).first()
            if not site:
                raise CommandError(f"Aucun site n’a l’identifiant {site_id}.")
            if slugs and "home" in slugs:
                raise CommandError("La page d’accueil d’un site est créée avec le site, par la commande create_site.")

            # These images are shared by all the sites: they are only imported if missing
            import_installed_images()
            self.create_pages(slugs or SITE_SLUGS, site)
            return

        call_command("import_dsfr_pictograms")
        call_command("import_illustration_images")

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

        # The default site is looked up by each page: creating the home page changes its root page
        self.create_pages(slugs)

    def create_pages(self, slugs: list, site: Site | None = None) -> None:
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

                self.create_page(slug=slug, title=title, body=body, site=site)
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
                self.create_page(
                    slug=slug, title=title, body=body, footer_label="Accessibilité : non conforme", site=site
                )
            elif slug == "contact":
                self.create_contact_page(slug, site=site)
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

        image = get_installed_image("Pictogrammes DSFR — Digital — Coding")
        text_raw = """<p>Bienvenue !</p>

        <p>Vous venez de créer un site utilisant le gestionnaire de contenus de l’État.</p>

        <p>Vous pouvez maintenant vous connecter dans l’administration et personnaliser le site.</p>
        """

        # Use the reversed admin path directly to avoid duplicating the script_name
        admin_url = reverse("wagtailadmin_home")

        image_and_text_block = {
            "image": {"image": image, "alt_text": "", "decorative": True},
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

    def get_existing_page(self, slug: str, site: Site) -> Page | None:
        """
        Returns the page of the site with the given slug: the other sites can have the same pages.
        """
        return Page.objects.descendant_of(site.root_page, inclusive=True).filter(slug=slug).first()

    def create_page(self, slug: str, title: str, body: list, footer_label: str = "", site: Site | None = None):
        """
        Creates a page for the site (by default, the default site) and adds it to the footer
        """
        site = site or get_default_site()

        # Don't replace a manually created page
        already_exists = self.get_existing_page(slug, site)
        if already_exists:
            self.stdout.write(f"The {slug} page seem to already exist with id {already_exists.id}")
            return

        home_page = site.root_page
        new_page = home_page.add_child(instance=ContentPage(title=title, body=body, slug=slug, show_in_menus=True))

        footer_menu = get_or_create_footer_bottom_menu(site)

        link_label = footer_label if footer_label else title

        link_value = {
            "text": link_label,
            "page": new_page,
            "link_type": "page",
        }
        footer_menu.items.append(("link", link_value))
        footer_menu.save()

        self.stdout.write(self.style.SUCCESS(f"Page {slug} created with id {new_page.id}"))

    def create_contact_page(self, slug: str = "contact", site: Site | None = None) -> None:
        """
        Creates a contact page for the site (by default, the default site) and adds it the main menu
        """
        site = site or get_default_site()

        # Don't replace a manually created page
        already_exists = self.get_existing_page(slug, site)
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

        home_page = site.root_page
        contact_page = home_page.add_child(
            instance=FormPage(title=title, slug=slug, intro=intro, thank_you_text=thank_you_text, show_in_menus=True)
        )

        # Create the form fields
        fields = [
            {
                "sort_order": 0,
                "clean_name": "votre_nom_complet",
                "autocomplete": "name",
                "label": "Votre nom complet",
                "required": True,
                "page": contact_page,
                "field_type": "singleline",
            },
            {
                "sort_order": 1,
                "clean_name": "votre_adresse_electronique",
                "autocomplete": "email",
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
                "autocomplete": "tel",
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
        main_menu = get_or_create_main_menu(site)

        link_value = {
            "text": title,
            "page": contact_page,
            "link_type": "page",
        }
        main_menu.items.append(("link", link_value))
        main_menu.save()

        self.stdout.write(self.style.SUCCESS(f"Form page {slug} created with id {contact_page.id}"))
