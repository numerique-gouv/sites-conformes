import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from sites_conformes.env import AutoConfig

ENV_FILE = """
DATABASE_USER=dju
DATABASE_HOST=localhost
DATABASE_URL=postgres://${DATABASE_USER}@${DATABASE_HOST}/${DATABASE_NAME:-djdb}
NESTED=${DATABASE_URL}?sslmode=require
UNKNOWN=a${NOT_DEFINED_ANYWHERE}b
LOOP=${LOOP}x
PLAIN=no reference
"""


class ExpandingAutoConfigTestCase(SimpleTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        Path(directory.name, ".env").write_text(ENV_FILE)
        self.config = AutoConfig(search_path=directory.name)

        # Make sure the variables from the developer's environment don't leak in
        names = ["DATABASE_USER", "DATABASE_HOST", "DATABASE_NAME", "DATABASE_URL", "NOT_DEFINED_ANYWHERE"]
        patcher = patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in names:
            os.environ.pop(name, None)

    def test_expands_references_from_the_file_and_defaults(self):
        self.assertEqual(self.config("DATABASE_URL"), "postgres://dju@localhost/djdb")

    def test_expands_nested_references(self):
        self.assertEqual(self.config("NESTED"), "postgres://dju@localhost/djdb?sslmode=require")

    def test_environment_wins_over_the_file(self):
        os.environ["DATABASE_USER"] = "env-user"
        os.environ["DATABASE_NAME"] = "env-db"
        self.assertEqual(self.config("DATABASE_URL"), "postgres://env-user@localhost/env-db")

    def test_environment_values_are_not_expanded(self):
        os.environ["DATABASE_URL"] = "postgres://${DATABASE_USER}"
        self.assertEqual(self.config("DATABASE_URL"), "postgres://${DATABASE_USER}")

    def test_unknown_reference_is_empty(self):
        self.assertEqual(self.config("UNKNOWN"), "ab")

    def test_self_reference_does_not_recurse(self):
        self.assertEqual(self.config("LOOP"), "x")

    def test_value_without_reference(self):
        self.assertEqual(self.config("PLAIN"), "no reference")
