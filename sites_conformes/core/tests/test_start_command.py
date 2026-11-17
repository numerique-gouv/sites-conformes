import json
import os
import subprocess  # nosec B404
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sites_conformes import __version__
from sites_conformes.cli import DEFAULT_FEATURES, Command

REPO_ROOT = Path(__file__).resolve().parents[3]


class StartCommandTestCase(unittest.TestCase):
    """
    The project template duplicates settings documented in docs/paquet/installation.md:
    this fails when a generated project stops working with the current package.
    """

    def manage(self, project: Path, *args: str) -> None:
        # A clean environment: the generated project must not see the settings
        # module or the database of the test run.
        env = {"PATH": os.environ["PATH"], "PYTHONPATH": str(REPO_ROOT)}
        result = subprocess.run(  # nosec B603
            [sys.executable, "manage.py", *args], cwd=project, env=env, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_generated_project_runs_on_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "monsite"
            project.mkdir()
            Command().run_from_argv(
                ["sites-conformes", "start", "monsite", str(project), "--no-input", "--verbosity", "0"]
            )

            self.assertIn(f"sites-conformes>={__version__}", (project / "pyproject.toml").read_text())
            self.assertIn("SECRET_KEY=", (project / ".env").read_text())
            self.assertTrue((project / ".gitignore").exists())
            self.assertFalse((project / "config.json").exists())
            settings = (project / "config" / "settings.py").read_text()
            for optional in ("proconnect", "dashboard", "db_storage", "wagtail_localize", "sentry"):
                self.assertNotIn(optional, settings)

            self.manage(project, "check")
            self.manage(project, "migrate", "--verbosity", "0")

    def start_with_answers(self, project: Path, **answers) -> None:
        # The prompts themselves need a terminal: only what is done with the answers is tested.
        defaults = {"site_title": "monsite", "site_tagline": "", "brand": "République française", "database_url": ""}
        with (
            mock.patch("sys.stdin.isatty", return_value=True),
            mock.patch.object(Command, "ask_customisations", return_value=defaults | DEFAULT_FEATURES | answers),
        ):
            Command().run_from_argv(["sites-conformes", "start", "monsite", str(project), "--verbosity", "0"])

    def test_answers_customise_the_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "monsite"
            project.mkdir()
            # Every feature on, with the storage that adds migrations: the largest settings file.
            self.start_with_answers(
                project,
                site_title="Mon site",
                brand="Ministère <test>",
                proconnect=True,
                two_fa=True,
                media_storage="db",
                languages=["en", "de"],
                sentry=True,
            )

            config = json.loads((project / "config.json").read_text())
            self.assertEqual(config["site_title"], "Mon site")
            self.assertEqual(config["header_brand"], "Ministère <test>")
            self.assertEqual(config["header_brand_html"], "Ministère &lt;test&gt;")

            env = (project / ".env").read_text()
            self.assertIn("PROCONNECT_CLIENT_ID=", env)
            self.assertIn("SENTRY_DSN=", env)

            settings = (project / "config" / "settings.py").read_text()
            for expected in (
                '"sites_conformes.proconnect"',
                '"sites_conformes.dashboard"',
                '"sites_conformes.db_storage"',
                '"wagtail_localize"',
                '("de", "Deutsch")',
                "WAGTAIL_2FA_REQUIRED = True",
                "sentry_sdk.init",
            ):
                self.assertIn(expected, settings)

            self.manage(project, "check")
            self.manage(project, "migrate", "--verbosity", "0")

    def test_database_url_answer_goes_to_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "monsite"
            project.mkdir()
            self.start_with_answers(project, database_url="postgres://u:p@localhost:5432/monsite")

            self.assertIn("DATABASE_URL=postgres://u:p@localhost:5432/monsite\n", (project / ".env").read_text())
            self.assertNotIn("sites_conformes.dashboard", (project / "config" / "settings.py").read_text())
