"""
Django management command to rename tables and update migration history.

This command:
1. Renames database tables by prefixing them with 'sites_conformes_'
2. Updates django_migrations to reflect the new app names
3. Updates django_content_type to reflect the new app labels

Safe to re-run: each step independently checks what remains to be done, so a
partial run (e.g. killed by a postdeploy timeout) is resumable. The whole
command runs inside a single transaction, so a hard kill mid-flight rolls
back instead of leaving a half-renamed schema.

Usage:
    python manage.py migrate_from_sites_faciles --no-input
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Rename tables and migrations to use sites_conformes_ prefix"

    APPS_TO_MIGRATE = ["blog", "events", "forms", "content_manager", "proconnect", "dashboard", "menus", "db_storage"]

    # Maps upstream app name → final app label (without the sites_conformes_ prefix).
    # e.g. "content_manager" → "sites_conformes_core_*".
    APP_RENAMES = {"content_manager": "core"}

    def _new_app_label(self, app: str) -> str:
        label = self.APP_RENAMES.get(app, app)
        return "sites_conformes_" + label

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without executing them",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Skip confirmation prompt (required in non-interactive contexts like Scalingo postdeploy)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        no_input = options["no_input"]

        self.stdout.write(self.style.SUCCESS("Starting database rename operations..."))
        self.stdout.write("=" * 60)

        with connection.cursor() as cursor:
            table_renames = self._plan_table_renames(cursor)
            migration_updates = self._plan_migration_updates(cursor)
            content_type_updates = self._plan_content_type_updates(cursor)

            self._report_plan(table_renames, migration_updates, content_type_updates)

            if not (table_renames or migration_updates or content_type_updates):
                self.stdout.write(self.style.SUCCESS("\nNothing to do — schema is already migrated."))
                return

            if dry_run:
                self.stdout.write("\n" + "=" * 60)
                self.stdout.write(self.style.SUCCESS("DRY RUN: No changes were made."))
                return

            if not no_input:
                self.stdout.write("\n" + "=" * 60)
                confirm = input("Proceed with renaming? (yes/no): ")
                if confirm.lower() != "yes":
                    self.stdout.write(self.style.WARNING("Operation cancelled."))
                    return

            with transaction.atomic():
                self._apply_table_renames(cursor, table_renames)
                self._apply_migration_updates(cursor, migration_updates)
                self._apply_content_type_updates(cursor, content_type_updates)

            self._verify(cursor)

            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS("✓ All operations completed successfully!"))

    # --- Planning (read-only) ----------------------------------------------

    def _plan_table_renames(self, cursor) -> list[tuple[str, str]]:
        like_clauses = " OR ".join([f"table_name LIKE '{app}_%'" for app in self.APPS_TO_MIGRATE])
        cursor.execute(f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND ({like_clauses})
            ORDER BY table_name;
            """)

        renames = []
        for (table_name,) in cursor.fetchall():
            owning_app = next(
                (app for app in self.APPS_TO_MIGRATE if table_name.startswith(f"{app}_")),
                None,
            )
            if owning_app:
                suffix = table_name[len(owning_app) :]
                new_name = self._new_app_label(owning_app) + suffix
            else:
                new_name = "sites_conformes_" + table_name
            renames.append((table_name, new_name))
        return renames

    def _plan_migration_updates(self, cursor) -> list[tuple[str, str, int]]:
        apps_in_clause = ", ".join([f"'{app}'" for app in self.APPS_TO_MIGRATE])
        cursor.execute(f"""
            SELECT app, COUNT(*) AS migration_count
            FROM django_migrations
            WHERE app IN ({apps_in_clause})
            GROUP BY app
            ORDER BY app;
            """)
        return [(app, self._new_app_label(app), count) for app, count in cursor.fetchall()]

    def _plan_content_type_updates(self, cursor) -> list[tuple[str, str, int]]:
        apps_in_clause = ", ".join([f"'{app}'" for app in self.APPS_TO_MIGRATE])
        cursor.execute(f"""
            SELECT app_label, COUNT(*) AS ct_count
            FROM django_content_type
            WHERE app_label IN ({apps_in_clause})
            GROUP BY app_label
            ORDER BY app_label;
            """)
        return [(app, self._new_app_label(app), count) for app, count in cursor.fetchall()]

    # --- Reporting ----------------------------------------------------------

    def _report_plan(self, table_renames, migration_updates, content_type_updates):
        self.stdout.write("\n1. Tables to rename:")
        if table_renames:
            for old, new in table_renames:
                self.stdout.write(f"  - {old} → {new}")
        else:
            self.stdout.write(self.style.WARNING("  (none — already renamed)"))

        self.stdout.write("\n2. Migration records to update:")
        if migration_updates:
            for app, new_app, count in migration_updates:
                self.stdout.write(f"  - {app}: {count} → {new_app}")
        else:
            self.stdout.write(self.style.WARNING("  (none — already updated)"))

        self.stdout.write("\n3. Content type records to update:")
        if content_type_updates:
            for app, new_app, count in content_type_updates:
                self.stdout.write(f"  - {app}: {count} → {new_app}")
        else:
            self.stdout.write(self.style.WARNING("  (none — already updated)"))

    # --- Apply (writes) -----------------------------------------------------

    def _apply_table_renames(self, cursor, table_renames):
        if not table_renames:
            return
        self.stdout.write("\nRenaming tables...")
        for old, new in table_renames:
            cursor.execute(f'ALTER TABLE "{old}" RENAME TO "{new}";')
            self.stdout.write(self.style.SUCCESS(f"  ✓ {old} → {new}"))

    def _apply_migration_updates(self, cursor, migration_updates):
        if not migration_updates:
            return
        self.stdout.write("\nUpdating django_migrations...")
        updated = 0
        for app, new_app, _count in migration_updates:
            cursor.execute(
                "UPDATE django_migrations SET app = %s WHERE app = %s;",
                [new_app, app],
            )
            updated += cursor.rowcount
        self.stdout.write(self.style.SUCCESS(f"  ✓ Updated {updated} migration records"))

    def _apply_content_type_updates(self, cursor, content_type_updates):
        if not content_type_updates:
            return
        self.stdout.write("\nUpdating django_content_type...")
        updated = 0
        for app, new_app, _count in content_type_updates:
            cursor.execute(
                "UPDATE django_content_type SET app_label = %s WHERE app_label = %s;",
                [new_app, app],
            )
            updated += cursor.rowcount
        self.stdout.write(self.style.SUCCESS(f"  ✓ Updated {updated} content type records"))

    # --- Verification -------------------------------------------------------

    def _verify(self, cursor):
        self.stdout.write("\nVerifying changes...")

        cursor.execute("""
            SELECT app, COUNT(*) AS count
            FROM django_migrations
            WHERE app LIKE 'sites_conformes_%'
            GROUP BY app
            ORDER BY app;
            """)
        results = cursor.fetchall()
        if results:
            self.stdout.write("Migration records after update:")
            for app, count in results:
                self.stdout.write(f"  - {app}: {count} migration(s)")

        cursor.execute("""
            SELECT app_label, COUNT(*) AS count
            FROM django_content_type
            WHERE app_label LIKE 'sites_conformes_%'
            GROUP BY app_label
            ORDER BY app_label;
            """)
        ct_results = cursor.fetchall()
        if ct_results:
            self.stdout.write("\nContent type records after update:")
            for app_label, count in ct_results:
                self.stdout.write(f"  - {app_label}: {count} model(s)")
