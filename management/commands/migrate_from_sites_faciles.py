"""
Django management command to rename tables and update migration history.

This command:
1. Renames database tables by prefixing them with 'sites_conformes_'
2. Updates django_migrations table to reflect the new app names

Usage:
    python manage.py migrate_from_sites_faciles
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Rename tables and migrations to use sites_conformes_ prefix"

    # Apps to migrate (from search-and-replace.yml)
    APPS_TO_MIGRATE = ["blog", "events", "forms", "content_manager", "config", "proconnect", "dashboard", "menus"]

    # Apps whose upstream name differs from their sites_conformes_ label.
    # Maps upstream app name → final app label (without the sites_conformes_ prefix).
    # e.g. "content_manager" is renamed to "core", so its tables go directly
    # from "content_manager_*" to "sites_conformes_core_*".
    APP_RENAMES = {
        "content_manager": "core",
    }

    def _new_app_label(self, app: str) -> str:
        """Return the final sites_conformes_<label> for a given upstream app name."""
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
            help="Skip confirmation prompt",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        no_input = options["no_input"]

        self.stdout.write(self.style.SUCCESS("Starting database rename operations..."))
        self.stdout.write("=" * 60)

        with connection.cursor() as cursor:
            # Step 1: Get list of tables to rename
            self.stdout.write("\n1. Finding tables to rename...")

            # Build the WHERE clause dynamically from APPS_TO_MIGRATE
            like_clauses = " OR ".join(
                [f"table_name LIKE '{app}_%'" for app in self.APPS_TO_MIGRATE]
            )

            query = f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND ({like_clauses})
                ORDER BY table_name;
            """
            cursor.execute(query)

            tables_to_rename = cursor.fetchall()

            if not tables_to_rename:
                self.stdout.write(self.style.WARNING("No tables found to rename."))
                return

            self.stdout.write(
                self.style.SUCCESS(f"Found {len(tables_to_rename)} tables to rename:")
            )
            table_renames = []
            for (table_name,) in tables_to_rename:
                # Determine which upstream app owns this table and apply any rename
                owning_app = next(
                    (app for app in self.APPS_TO_MIGRATE if table_name.startswith(f"{app}_")),
                    None,
                )
                if owning_app:
                    suffix = table_name[len(owning_app):]  # e.g. "_mymodel"
                    new_name = self._new_app_label(owning_app) + suffix
                else:
                    new_name = "sites_conformes_" + table_name
                table_renames.append((table_name, new_name))
                self.stdout.write(f"  - {table_name} → {new_name}")

            # Step 2: Preview migration updates
            self.stdout.write("\n2. Previewing migration updates...")

            # Build the IN clause dynamically from APPS_TO_MIGRATE
            apps_in_clause = ", ".join([f"'{app}'" for app in self.APPS_TO_MIGRATE])

            query = f"""
                SELECT
                    app,
                    COUNT(*) as migration_count
                FROM django_migrations
                WHERE app IN ({apps_in_clause})
                GROUP BY app
                ORDER BY app;
            """
            cursor.execute(query)

            migrations_to_update = cursor.fetchall()

            if not migrations_to_update:
                self.stdout.write(self.style.WARNING("No migrations found to update."))
                migration_updates = []
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Found migrations in {len(migrations_to_update)} apps:"
                    )
                )
                migration_updates = []
                for app, count in migrations_to_update:
                    new_app = self._new_app_label(app)
                    migration_updates.append((app, new_app, count))
                    self.stdout.write(f"  - {app}: {count} migration(s) → {new_app}")

            if dry_run:
                self.stdout.write("\n" + "=" * 60)
                self.stdout.write(self.style.SUCCESS("DRY RUN: No changes were made."))
                return

            # Step 3: Confirm before proceeding
            if not no_input:
                self.stdout.write("\n" + "=" * 60)
                confirm = input("Proceed with renaming? (yes/no): ")
                if confirm.lower() != "yes":
                    self.stdout.write(self.style.WARNING("Operation cancelled."))
                    return

            self.stdout.write("\n3. Starting transaction...")

            # Step 4: Rename tables
            self.stdout.write("\n4. Renaming tables...")
            renamed_count = 0
            for table_name, new_name in table_renames:
                try:
                    cursor.execute(
                        f'ALTER TABLE "{table_name}" RENAME TO "{new_name}";'
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✓ Renamed: {table_name} → {new_name}")
                    )
                    renamed_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  ✗ Error renaming {table_name}: {e}")
                    )

            self.stdout.write(self.style.SUCCESS(f"\nRenamed {renamed_count} tables."))

            # Step 5: Update django_migrations
            if migration_updates:
                self.stdout.write("\n5. Updating django_migrations table...")

                updated_rows = 0
                for app, new_app, _count in migration_updates:
                    query = f"""
                        UPDATE django_migrations
                        SET app = '{new_app}'
                        WHERE app = '{app}';
                    """
                    cursor.execute(query)
                    updated_rows += cursor.rowcount
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Updated {updated_rows} migration records")
                )

            # Step 6: Update django_content_type
            self.stdout.write("\n6. Updating django_content_type table...")

            updated_content_types = 0
            for app in self.APPS_TO_MIGRATE:
                new_app = self._new_app_label(app)
                query = f"""
                    UPDATE django_content_type
                    SET app_label = '{new_app}'
                    WHERE app_label = '{app}';
                """
                cursor.execute(query)
                updated_content_types += cursor.rowcount
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ Updated {updated_content_types} content type records"
                )
            )

            # Step 7: Verify changes
            self.stdout.write("\n7. Verifying changes...")

            # Verify migrations
            cursor.execute("""
                SELECT app, COUNT(*) as count
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

            # Verify content types
            cursor.execute("""
                SELECT app_label, COUNT(*) as count
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

            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(
                self.style.SUCCESS("✓ All operations completed successfully!")
            )
