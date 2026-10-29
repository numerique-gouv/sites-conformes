from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from sites_conformes.core.management.commands.migrate_from_sites_faciles import Command

COMMAND_MODULE = "sites_conformes.core.management.commands.migrate_from_sites_faciles"


def table_exists(table_name):
    return table_name in connection.introspection.table_names()


def count_rows(query, params):
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchone()[0]


class FreshDatabaseTestCase(TestCase):
    def test_fresh_database_is_skipped(self):
        """The test database already has the sites_conformes_ tables, so nothing should be done."""
        out = StringIO()
        call_command("migrate_from_sites_faciles", "--no-input", stdout=out)

        self.assertIn("Fresh database", out.getvalue())


class LegacySchemaTestCase(TestCase):
    """
    Simulate a legacy Sites Faciles schema, with tables, migration records and content types
    not yet prefixed with sites_conformes_
    """

    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE "blog_legacytest" (id serial PRIMARY KEY);')
            cursor.execute('CREATE TABLE "content_manager_legacytest" (id serial PRIMARY KEY);')
            cursor.execute(
                "INSERT INTO django_migrations (app, name, applied) VALUES "
                "('blog', '0001_initial', NOW()), ('blog', '0002_legacy', NOW()), "
                "('content_manager', '0001_initial', NOW());"
            )
            cursor.execute(
                "INSERT INTO django_content_type (app_label, model) VALUES "
                "('blog', 'legacytest'), ('content_manager', 'legacytest');"
            )

        # The real test database is already migrated: only report the legacy schema detection check
        patcher = patch.object(Command, "_table_exists", side_effect=lambda cursor, name: name == "django_migrations")
        patcher.start()
        self.addCleanup(patcher.stop)

    def call_command(self, *args):
        out = StringIO()
        call_command("migrate_from_sites_faciles", *args, stdout=out)
        return out.getvalue()

    def count_migrations(self, app):
        return count_rows("SELECT COUNT(*) FROM django_migrations WHERE app = %s;", [app])

    def count_content_types(self, app_label):
        return count_rows("SELECT COUNT(*) FROM django_content_type WHERE app_label = %s;", [app_label])

    def assert_legacy_schema_unchanged(self):
        self.assertTrue(table_exists("blog_legacytest"))
        self.assertTrue(table_exists("content_manager_legacytest"))
        self.assertEqual(self.count_migrations("blog"), 2)
        self.assertEqual(self.count_content_types("content_manager"), 1)

    def test_dry_run_changes_nothing(self):
        output = self.call_command("--dry-run")

        self.assertIn("blog_legacytest → sites_conformes_blog_legacytest", output)
        self.assertIn("content_manager_legacytest → sites_conformes_core_legacytest", output)
        self.assertIn("blog: 2 → sites_conformes_blog", output)
        self.assertIn("DRY RUN", output)
        self.assert_legacy_schema_unchanged()

    def test_cancelled_without_confirmation(self):
        with patch("builtins.input", return_value="no"):
            output = self.call_command()

        self.assertIn("Operation cancelled.", output)
        self.assert_legacy_schema_unchanged()

    def test_schema_is_migrated(self):
        output = self.call_command("--no-input")

        self.assertIn("All operations completed successfully", output)

        self.assertFalse(table_exists("blog_legacytest"))
        self.assertFalse(table_exists("content_manager_legacytest"))
        self.assertTrue(table_exists("sites_conformes_blog_legacytest"))
        self.assertTrue(table_exists("sites_conformes_core_legacytest"))

        self.assertEqual(self.count_migrations("blog"), 0)
        self.assertEqual(self.count_migrations("content_manager"), 0)
        self.assertEqual(
            count_rows(
                "SELECT COUNT(*) FROM django_migrations WHERE app = %s AND name = %s;",
                ["sites_conformes_blog", "0002_legacy"],
            ),
            1,
        )

        self.assertEqual(self.count_content_types("blog"), 0)
        self.assertEqual(self.count_content_types("content_manager"), 0)
        self.assertEqual(
            count_rows(
                "SELECT COUNT(*) FROM django_content_type WHERE app_label = %s AND model = %s;",
                ["sites_conformes_core", "legacytest"],
            ),
            1,
        )

    def test_second_run_has_nothing_to_do(self):
        self.call_command("--no-input")

        output = self.call_command("--no-input")

        self.assertIn("Nothing to do", output)
