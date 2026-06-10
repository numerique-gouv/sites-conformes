"""
Phased migration from Sites Conformes blog pages to publications.

Run each phase separately after verifying the previous one on staging::

    python manage.py migrate_blog_to_publications --phase=1 --dry-run
    python manage.py migrate_blog_to_publications --phase=1
    python manage.py migrate_blog_to_publications --phase=2
    python manage.py migrate_blog_to_publications --phase=3
    python manage.py migrate_blog_to_publications --phase=4

See ``publications/migrations/data_migrations/migrate_from_blog.py`` for design
notes (ContentType, PKs, blog blocks, link rewriting).

Each phase is atomic: a failure rolls back that phase only, not earlier phases.

On production, consider disabling or hiding the Wagtail admin during the run so
no one edits pages while types and stream fields are being rewritten.
"""

from django.core.management.base import BaseCommand, CommandError

from publications.migrations.data_migrations.migrate_from_blog import (
    MigrationConfig,
    blog_index_scope_label,
    run_phase,
)


class Command(BaseCommand):
    help = "Migrate BlogIndexPage/BlogEntryPage to publications (four phases)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--phase",
            type=int,
            choices=[1, 2, 3, 4],
            help="1=pages, 2=taxonomies, 3=assign taxonomies, 4=fix embedded links",
        )
        parser.add_argument(
            "--all-phases",
            action="store_true",
            help="Run phases 1–4 in order (idempotent; safe on every deploy).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Log actions without writing to the database.",
        )
        parser.add_argument(
            "--blog-index-slug",
            action="append",
            dest="blog_index_slugs",
            help="Limit migration to these blog index slugs (repeatable; default: all indexes).",
        )

    def handle(self, *args, **options):
        config = MigrationConfig()
        if options["blog_index_slugs"]:
            config.blog_index_slugs = options["blog_index_slugs"]

        dry_run = options["dry_run"]
        phases = [1, 2, 3, 4] if options["all_phases"] else [options["phase"]]
        if not phases or phases == [None]:
            raise CommandError("Pass --phase or --all-phases.")

        for phase in phases:
            self.stdout.write(
                self.style.NOTICE(
                    f"Phase {phase} — blog indexes: {blog_index_scope_label(config)}",
                ),
            )
            try:
                report = run_phase(phase, config, dry_run=dry_run)
            except Exception as exc:
                raise CommandError(str(exc)) from exc

            self.stdout.write(
                self.style.SUCCESS(f"Phase {report.phase} finished ({len(report.messages)} log lines)."),
            )
