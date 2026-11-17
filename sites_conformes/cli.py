"""
Entry point of the `sites-conformes` command.

`sites-conformes start <name>` creates a minimal Django/Wagtail project using the
package, the way `wagtail start` does: Django's `startproject` with our template.
"""

import json
import sys
import time
from html import escape
from pathlib import Path

from django.conf.locale import LANG_INFO
from django.core.management.commands.startproject import Command as StartProject
from django.core.management.utils import get_random_secret_key

from sites_conformes import __version__

USAGE = "Usage : sites-conformes start <nom_du_projet> [dossier]"

# Offered as checkboxes; any other language is one more line in LANGUAGES of the settings.
EXTRA_LANGUAGES = ("en", "de", "es", "it", "pt", "nl")
# What `--no-input` generates: the smallest working project.
DEFAULT_FEATURES = {"proconnect": False, "two_fa": False, "media_storage": "files", "languages": [], "sentry": False}

# Values to fill in, appended to the `.env` of the project for the chosen features.
ENV_PROCONNECT = """
# ProConnect : identifiants fournis par https://partenaires.proconnect.gouv.fr/
PROCONNECT_CLIENT_ID=
PROCONNECT_CLIENT_SECRET=
PROCONNECT_DOMAIN=fca.integ01.dev-agentconnect.fr
"""
ENV_S3 = """
# Stockage S3 des médias
S3_HOST=
S3_KEY_ID=
S3_KEY_SECRET=
S3_BUCKET_NAME=
S3_BUCKET_REGION=
S3_LOCATION=medias
"""
ENV_SENTRY = """
# Sentry : sans DSN, rien n’est envoyé
SENTRY_DSN=
SENTRY_ENVIRONMENT=development
"""

# Keep in sync with project_template/README.md.
NEXT_STEPS = """
Pour lancer le site :

  cd {target}
  uv run python manage.py migrate
  uv run python manage.py collectstatic --noinput
  uv run python manage.py create_starter_pages
  uv run python manage.py createsuperuser
  uv run python manage.py runserver

Le site sera sur http://localhost:8000/ et l’administration sur http://localhost:8000/cms-admin/
"""


class Command(StartProject):
    help = "Crée un projet Sites Conformes minimal."

    def add_arguments(self, parser) -> None:
        super().add_arguments(parser)
        parser.add_argument(
            "--no-input",
            action="store_false",
            dest="interactive",
            help="Ne pose aucune question.",
        )

    def ask_customisations(self, name: str) -> dict:
        # Only needed here, not by the sites that install the package.
        import questionary

        style = questionary.Style(
            [
                ("qmark", "fg:#6a6af4 bold"),
                ("question", "bold"),
                ("answer", "fg:#6a6af4"),
                ("pointer", "fg:#6a6af4 bold"),
                ("highlighted", "fg:#6a6af4"),
                ("selected", "fg:#6a6af4"),
                ("instruction", "fg:#888888"),
            ]
        )

        def ask(prompt, question: str, **kwargs):
            # unsafe_ask: let Ctrl+C reach handle(), which stops before creating anything.
            return prompt(question, style=style, qmark="?", **kwargs).unsafe_ask()

        self.stdout.write("")
        animate_minitel()
        questionary.print(f"\n  Sites Conformes {__version__}", style="bold fg:#6a6af4")
        questionary.print("  Quelques questions pour créer votre site.\n", style="fg:#888888")

        answers = {
            "site_title": ask(questionary.text, "Titre du site", default=name),
            "site_tagline": ask(questionary.text, "Sous-titre du site", instruction="(facultatif) "),
            "brand": ask(questionary.text, "Intitulé officiel sous la Marianne", default="République française"),
        }
        postgres = ask(
            questionary.select,
            "Base de données",
            instruction="(flèches pour choisir)",
            choices=[
                questionary.Choice("SQLite, rien à installer", False),
                questionary.Choice("PostgreSQL", True),
            ],
        )
        answers["database_url"] = (
            ask(questionary.text, "URL de la base", default="postgres://utilisateur:motdepasse@localhost:5432/" + name)
            if postgres
            else ""
        )
        answers["media_storage"] = ask(
            questionary.select,
            "Stockage des images et documents",
            instruction="(flèches pour choisir)",
            choices=[
                questionary.Choice("Fichiers locaux, pour le développement uniquement", "files"),
                questionary.Choice("Base de données, pratique sur un PaaS jusqu’à 1 Go", "db"),
                questionary.Choice("Bucket S3", "s3"),
            ],
        )
        features = ask(
            questionary.checkbox,
            "Fonctionnalités à activer",
            instruction="(espace pour cocher, entrée pour valider)",
            choices=[
                questionary.Choice("Connexion à l’administration avec ProConnect", "proconnect"),
                questionary.Choice("Double authentification obligatoire", "two_fa"),
                questionary.Choice("Suivi des erreurs avec Sentry", "sentry"),
            ],
        )
        answers["languages"] = ask(
            questionary.checkbox,
            "Langues en plus du français",
            instruction="(espace pour cocher, entrée pour valider)",
            choices=[questionary.Choice(LANG_INFO[code]["name_local"].capitalize(), code) for code in EXTRA_LANGUAGES],
        )
        return answers | {feature: feature in features for feature in ("proconnect", "two_fa", "sentry")}

    def handle(self, **options) -> None:
        name = options["name"]
        target = Path(options["directory"] or name)
        # Asked before creating anything, so that Ctrl+C leaves no half-made project.
        interactive = options["interactive"] and sys.stdin.isatty()
        try:
            answers = self.ask_customisations(name) if interactive else {}
        except KeyboardInterrupt:
            sys.exit("\nCréation annulée : rien n’a été créé.")
        features = {key: answers.get(key, default) for key, default in DEFAULT_FEATURES.items()}

        options["template"] = str(Path(__file__).parent / "project_template")
        options["files"] = ["pyproject.toml", "README.md"]  # rendered like the .py files
        options["sites_conformes_version"] = __version__
        # The settings and URLs only contain the blocks of the chosen features.
        options |= features
        # The ProConnect button lives in the login page of the dashboard app, like the 2FA screens.
        options["dashboard"] = features["proconnect"] or features["two_fa"]
        options["languages"] = [(code, LANG_INFO[code]["name_local"].capitalize()) for code in features["languages"]]
        super().handle(**options)

        # Not a template file: a `.env` inside the package would be git-ignored.
        env = f"DEBUG=True\nSECRET_KEY={get_random_secret_key()}\n"
        if answers.get("database_url"):
            env += f"DATABASE_URL={answers['database_url']}\n"
        if features["proconnect"]:
            env += ENV_PROCONNECT
        if features["media_storage"] == "s3":
            env += ENV_S3
        if features["sentry"]:
            env += ENV_SENTRY
        (target / ".env").write_text(env)

        if answers:
            # Read by `set_config`, which `create_starter_pages` runs on a new site.
            brand = answers["brand"]
            config = {
                "site_title": answers["site_title"],
                "site_tagline": answers["site_tagline"],
                "header_brand": brand,
                "header_brand_html": escape(brand),
                "footer_brand": brand,
                "footer_brand_html": escape(brand),
            }
            (target / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")

        if options["verbosity"] > 0:
            self.stdout.write(self.style.SUCCESS(f"\n✔ Projet créé dans {target}/"))
            for line in created_summary(features):
                self.stdout.write(f"  {line}")
            self.stdout.write(NEXT_STEPS.format(target=target))


SCREEN_WIDTH = 22
SCREEN_HEIGHT = 4
FLAG_BANDS = (("0;0;145", 7), ("255;255;255", 8), ("225;0;15", 7))  # DSFR blue France, white, red Marianne
MINITEL = """\
   ╭──────────────────────────╮
   │ ╭──────────────────────╮ │
{screen}
   │ ╰──────────────────────╯ │
   │                    ▪ ▪ ▪ │
   ╰──────────────────────────╯
    ╱ ▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫  ▫▫▫ ╲
   ╱  ▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫  ▫▫▫  ╲
  ╰────────────────────────────╯
"""


def flag_row(columns: int) -> str:
    """One screen row with the first `columns` cells of the blue, white and red bands."""
    row, start = "", 0
    for colour, width in FLAG_BANDS:
        row += f"\x1b[38;2;{colour}m{'█' * max(0, min(width, columns - start))}"
        start += width
    return f"{row}\x1b[0m{' ' * (SCREEN_WIDTH - columns)}"


def text_rows(typed: str) -> list[str]:
    """The screen showing what has been typed so far of "3615 / SITES CONFORMES", with a cursor."""
    first, _, second = typed.partition("\n")
    rows = ["", f"   {first}", f"   {second}", ""]
    rows[2 if "\n" in typed else 1] += "█"
    return [f"\x1b[1m{row.ljust(SCREEN_WIDTH)}\x1b[0m" for row in rows]


def minitel_frames() -> list[tuple[list[str], float]]:
    """Screen rows and duration of each frame: the flag wipes in, then the service name is typed."""
    frames = [([flag_row(columns)] * SCREEN_HEIGHT, 0.02) for columns in range(1, SCREEN_WIDTH + 1)]
    frames[-1] = (frames[-1][0], 0.4)
    message = "3615\nSITES CONFORMES"
    frames += [(text_rows(message[:length]), 0.04) for length in range(len(message) + 1)]
    return frames


def animate_minitel(stream=sys.stdout, sleep=time.sleep) -> None:
    """Draws a Minitel whose screen plays the flag, then shows "3615 SITES CONFORMES"."""
    height = MINITEL.count("\n") + SCREEN_HEIGHT - 1
    stream.write("\x1b[?25l")  # hide the cursor while redrawing
    try:
        for index, (rows, duration) in enumerate(minitel_frames()):
            if index:
                stream.write(f"\x1b[{height}A")  # back to the top of the previous frame
            stream.write(MINITEL.format(screen="\n".join(f"   │ │{row}│ │" for row in rows)))
            stream.flush()
            sleep(duration)
    finally:
        stream.write("\x1b[?25h")


def created_summary(features: dict) -> list[str]:
    """What the generated project contains, so that the choices can be checked at a glance."""
    storage = {
        "files": "fichiers locaux (développement uniquement)",
        "db": "base de données",
        "s3": "bucket S3 (variables S3_* à remplir)",
    }
    lines = [f"Médias : {storage[features['media_storage']]}"]
    if features["proconnect"]:
        lines.append("ProConnect : variables PROCONNECT_* à remplir dans .env")
    if features["two_fa"]:
        lines.append("Double authentification obligatoire")
    if features["languages"]:
        lines.append(f"Langues : fr, {', '.join(features['languages'])}")
    if features["sentry"]:
        lines.append("Sentry : SENTRY_DSN à remplir dans .env")
    return lines


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] != "start":
        sys.exit(USAGE)
    Command().run_from_argv(sys.argv)


if __name__ == "__main__":
    main()
