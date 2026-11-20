import os
import subprocess
import sys
import tempfile
from io import StringIO
from unittest import mock, skipUnless
from urllib.parse import quote

from django.conf import settings
from django.core.management import get_commands
from django.db import connection, migrations, models
from django.test import SimpleTestCase
from wagtail import blocks
from wagtail.fields import StreamField

from sites_conformes.core.management.commands.migrate import Command


def stream_field():
    """
    Returns a StreamField whose blocks are built and cached, as after the rendering of a migration state
    """
    field = StreamField([("text", blocks.CharBlock())], blank=True)
    field.stream_block  # noqa: B018
    return field


def is_cached(field):
    return "stream_block" in field.__dict__


def make_migration(name, operations, app_label="sites_conformes_core"):
    migration = migrations.Migration(name, app_label)
    migration.operations = operations
    return migration


class MigrateCommandTestCase(SimpleTestCase):
    def setUp(self):
        self.command = Command(stdout=StringIO())
        self.command.verbosity = 0

        # Only runs the initialization of the command, not the actual migrations
        with mock.patch("django.core.management.commands.migrate.Command.handle"):
            self.command.handle()

    def apply(self, migration):
        self.command.migration_progress_callback("apply_start", migration)
        self.command.migration_progress_callback("apply_success", migration)

    def test_command_overrides_django_migrate(self):
        self.assertEqual(get_commands()["migrate"], "sites_conformes.core")

    def test_superseded_field_cache_is_dropped(self):
        old_field = stream_field()
        new_field = stream_field()

        self.apply(make_migration("0001", [migrations.AddField("contentpage", "body", old_field)]))
        self.assertTrue(is_cached(old_field))

        self.apply(make_migration("0002", [migrations.AlterField("contentpage", "body", new_field)]))
        self.assertFalse(is_cached(old_field))
        self.assertTrue(is_cached(new_field))

    def test_create_model_fields_are_cleared(self):
        old_field = stream_field()
        new_field = stream_field()

        self.apply(make_migration("0001", [migrations.CreateModel("ContentPage", [("body", old_field)])]))
        self.apply(make_migration("0002", [migrations.AlterField("contentpage", "body", new_field)]))

        self.assertFalse(is_cached(old_field))
        self.assertTrue(is_cached(new_field))

    def test_field_cache_cleared_again_after_new_render(self):
        old_field = stream_field()

        self.apply(make_migration("0001", [migrations.AddField("contentpage", "body", old_field)]))
        self.apply(make_migration("0002", [migrations.AlterField("contentpage", "body", stream_field())]))

        # A later render of a previous state builds the blocks again
        old_field.stream_block  # noqa: B018
        self.apply(make_migration("0003", [migrations.RunPython(migrations.RunPython.noop)]))

        self.assertFalse(is_cached(old_field))

    def test_other_fields_are_kept(self):
        body = stream_field()
        hero = stream_field()
        blog_body = stream_field()

        self.apply(
            make_migration(
                "0001",
                [
                    migrations.AddField("contentpage", "body", body),
                    migrations.AddField("contentpage", "hero", hero),
                    migrations.AddField("catalogindexpage", "body", stream_field()),
                ],
            )
        )
        self.apply(make_migration("0001", [migrations.AddField("blogentrypage", "body", blog_body)], "blog"))
        self.apply(make_migration("0002", [migrations.AlterField("catalogindexpage", "body", stream_field())]))

        self.assertTrue(is_cached(body))
        self.assertTrue(is_cached(hero))
        self.assertTrue(is_cached(blog_body))

    def test_other_operations_are_ignored(self):
        self.apply(
            make_migration(
                "0001",
                [
                    migrations.AddField("contentpage", "title", models.CharField(max_length=255)),
                    migrations.RunPython(migrations.RunPython.noop),
                    migrations.DeleteModel("OldPage"),
                ],
            )
        )

        self.assertEqual(len(self.command.done_migrations), 1)

    def test_caches_are_kept_until_migration_success(self):
        old_field = stream_field()

        self.apply(make_migration("0001", [migrations.AddField("contentpage", "body", old_field)]))
        self.command.migration_progress_callback(
            "apply_start", make_migration("0002", [migrations.AlterField("contentpage", "body", stream_field())])
        )

        self.assertTrue(is_cached(old_field))
        self.assertEqual(len(self.command.done_migrations), 1)

    def test_unapplied_migrations_are_cleared(self):
        old_field = stream_field()

        self.apply(make_migration("0001", [migrations.AddField("contentpage", "body", old_field)]))
        self.command.migration_progress_callback(
            "unapply_success", make_migration("0002", [migrations.AlterField("contentpage", "body", stream_field())])
        )

        self.assertFalse(is_cached(old_field))

    def test_blocks_created_during_migrations_are_unregistered(self):
        # Created before the migrations: blocks of the actual models must stay available
        existing_block = blocks.CharBlock()
        # The command is initialized again to include the block created above
        with mock.patch("django.core.management.commands.migrate.Command.handle"):
            self.command.handle()

        migration_block = blocks.CharBlock()
        self.assertIn(migration_block.definition_prefix, blocks.Block.definition_registry)

        self.apply(make_migration("0001", []))

        self.assertNotIn(migration_block.definition_prefix, blocks.Block.definition_registry)
        self.assertIs(blocks.Block.definition_registry[existing_block.definition_prefix], existing_block)


class MigrateSqliteTestCase(SimpleTestCase):
    def test_migrations_run_on_sqlite(self):
        # The tests run on PostgreSQL, but projects installing the package may use SQLite,
        # which rejects some of the SQL that PostgreSQL accepts in a RunSQL operation
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "manage.py", "migrate", "--verbosity", "0"],
                cwd=settings.BASE_DIR,
                env={**os.environ, "DATABASE_URL": f"sqlite:///{directory}/db.sqlite3"},
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)


# Memory of the containers running the postdeploy hook on Scalingo (size M)
MIGRATE_MEMORY_LIMIT_MB = 512

# Runs all the migrations on an empty database and prints the peak memory used, in MB
MIGRATE_MEMORY_SCRIPT = """
import resource, sys
import django
django.setup()
from django.core.management import call_command
call_command("migrate", verbosity=0)
max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
# ru_maxrss is in bytes on macOS and in kilobytes elsewhere
print(max_rss / 1024 / (1024 if sys.platform == "darwin" else 1))
"""


@skipUnless(os.getenv("RUN_RELEASE_TESTS"), "Slow test, only run when preparing a release (`just test-release`)")
class MigrateMemoryTestCase(SimpleTestCase):
    databases = {"default"}

    def setUp(self):
        db = connection.settings_dict
        self.database_name = f"{db['NAME']}_migrate_memory"
        self.database_url = (
            f"postgres://{quote(db['USER'] or '')}:{quote(db['PASSWORD'] or '')}"
            f"@{db['HOST'] or 'localhost'}:{db['PORT'] or 5432}/{self.database_name}"
        )
        with connection.cursor() as cursor:
            cursor.execute(f'DROP DATABASE IF EXISTS "{self.database_name}"')
            cursor.execute(f'CREATE DATABASE "{self.database_name}"')

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute(f'DROP DATABASE IF EXISTS "{self.database_name}"')

    def test_migrate_stays_under_container_memory(self):
        # Run in a separate process, which starts with an empty memory like on Scalingo
        result = subprocess.run(
            [sys.executable, "-c", MIGRATE_MEMORY_SCRIPT],
            cwd=settings.BASE_DIR,
            env={**os.environ, "DATABASE_URL": self.database_url},
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        max_memory_mb = float(result.stdout.strip().splitlines()[-1])
        self.assertLess(max_memory_mb, MIGRATE_MEMORY_LIMIT_MB)
