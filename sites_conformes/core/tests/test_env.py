import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from sites_conformes.env import read_env

ENV_FILE = """
DATABASE_USER=dju
DATABASE_HOST=localhost
DATABASE_URL=postgres://${DATABASE_USER}@${DATABASE_HOST}/${DATABASE_NAME:-djdb}
NESTED=${DATABASE_URL}?sslmode=require
UNKNOWN=a${NOT_DEFINED_ANYWHERE}b
LOOP=${LOOP}x
PLAIN=no reference
"""

NAMES = [
    "DATABASE_USER",
    "DATABASE_HOST",
    "DATABASE_NAME",
    "DATABASE_URL",
    "NESTED",
    "UNKNOWN",
    "LOOP",
    "PLAIN",
    "NOT_DEFINED_ANYWHERE",
]


class ReadEnvTestCase(SimpleTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.env_file = Path(directory.name, ".env")
        self.env_file.write_text(ENV_FILE)

        # Restore os.environ after each test, and make sure the developer's environment doesn't leak in
        patcher = patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in NAMES:
            os.environ.pop(name, None)

    def test_expands_references_from_the_file_and_defaults(self):
        read_env(self.env_file)
        self.assertEqual(os.environ["DATABASE_URL"], "postgres://dju@localhost/djdb")

    def test_expands_nested_references(self):
        read_env(self.env_file)
        self.assertEqual(os.environ["NESTED"], "postgres://dju@localhost/djdb?sslmode=require")

    def test_environment_wins_over_the_file(self):
        os.environ["DATABASE_USER"] = "env-user"
        os.environ["DATABASE_NAME"] = "env-db"
        read_env(self.env_file)
        self.assertEqual(os.environ["DATABASE_USER"], "env-user")
        self.assertEqual(os.environ["DATABASE_URL"], "postgres://env-user@localhost/env-db")

    def test_environment_values_are_not_expanded(self):
        os.environ["DATABASE_URL"] = "postgres://${DATABASE_USER}"
        read_env(self.env_file)
        self.assertEqual(os.environ["DATABASE_URL"], "postgres://${DATABASE_USER}")

    def test_unknown_reference_is_empty(self):
        read_env(self.env_file)
        self.assertEqual(os.environ["UNKNOWN"], "ab")

    def test_self_reference_does_not_recurse(self):
        read_env(self.env_file)
        self.assertEqual(os.environ["LOOP"], "x")

    def test_value_without_reference(self):
        read_env(self.env_file)
        self.assertEqual(os.environ["PLAIN"], "no reference")

    def test_missing_file_is_ignored(self):
        read_env(self.env_file.with_name("missing.env"))
        self.assertNotIn("PLAIN", os.environ)
