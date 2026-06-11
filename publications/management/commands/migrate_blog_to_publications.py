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

By default, output is written to stdout and to a timestamped log file under
``publications/migrations/data_migrations/output/``. Use ``--no-log-file`` for stdout only.

Phases 1–4 prompt for confirmation (scope summary for 1–3). Pass ``--no-input`` to skip
prompts (e.g. postdeploy).

On production, consider disabling or hiding the Wagtail admin during the run so
no one edits pages while types and stream fields are being rewritten.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from wagtail.models import Locale

from publications.migrations.data_migrations.migrate_from_blog import (
    MigrationConfig,
    blog_index_scope_label,
    format_assign_taxonomies_summary,
    format_blog_index_summaries,
    format_taxonomy_migration_summary,
    get_assign_taxonomies_summary,
    get_blog_index_summaries,
    get_taxonomy_migration_summary,
    migration_log_path,
    resolve_migration_locale,
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
        parser.add_argument(
            "--locale",
            dest="locale_language_code",
            default=None,
            help="Wagtail language code for slug lookups (default: site default locale).",
        )
        parser.add_argument(
            "--log-file",
            default=None,
            help=(
                "Log file path (default: publications/migrations/data_migrations/output/"
                "migrate_blog_to_publications_<timestamp>.log)."
            ),
        )
        parser.add_argument(
            "--no-log-file",
            action="store_true",
            help="Do not write migration output to a log file (stdout only).",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Do not prompt for confirmation before phases 1–4.",
        )

    def handle(self, *args, **options):
        config = MigrationConfig()
        if options["blog_index_slugs"]:
            config.blog_index_slugs = options["blog_index_slugs"]
        if options["locale_language_code"]:
            config.locale_language_code = options["locale_language_code"]

        try:
            resolve_migration_locale(config)
        except Locale.DoesNotExist:
            if config.locale_language_code:
                raise CommandError(f"Unknown locale: {config.locale_language_code!r}") from None
            raise CommandError("No Wagtail locale configured.") from None

        dry_run = options["dry_run"]
        phases = [1, 2, 3, 4] if options["all_phases"] else [options["phase"]]
        if not phases or phases == [None]:
            raise CommandError("Pass --phase or --all-phases.")

        log_file = None
        if not options["no_log_file"]:
            started_at = timezone.now()
            log_path = migration_log_path(override=options["log_file"], started_at=started_at)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = log_path.open("w", encoding="utf-8", buffering=1)
            log_file.write(
                f"--- migrate_blog_to_publications {started_at.isoformat()} "
                f"(dry_run={dry_run}, phases={phases}) ---\n",
            )
            log_file.flush()
            self.stdout.write(self.style.NOTICE(f"Logging to {log_path}"))

        log_stdout = self._log_stdout_writer()

        try:
            for phase in phases:
                if not options["no_input"]:
                    self._prompt_for_phase(phase, config, log_file)

                phase_header = f"Phase {phase} — blog indexes: {blog_index_scope_label(config)}"
                self._write_line(phase_header, log_file, style=self.style.NOTICE)

                try:
                    report = run_phase(
                        phase,
                        config,
                        dry_run=dry_run,
                        log_file=log_file,
                        log_stdout=log_stdout,
                    )
                except Exception as exc:
                    raise CommandError(str(exc)) from exc

                summary = f"Phase {report.phase} finished ({len(report.messages)} log lines)."
                self._write_line(summary, log_file, style=self.style.SUCCESS)
        finally:
            if log_file is not None:
                log_file.close()

    def _log_stdout_writer(self):
        def write(line: str) -> None:
            self.stdout.write(line)
            self.stdout.flush()

        return write

    def _write_line(self, line, log_file, style=None):
        if style is None:
            self.stdout.write(line)
        else:
            self.stdout.write(style(line))
        self.stdout.flush()
        if log_file is not None:
            log_file.write(line + "\n")
            log_file.flush()

    def _prompt_for_phase(self, phase, config, log_file):
        if phase == 1:
            lines = format_blog_index_summaries(get_blog_index_summaries(config))
            prompt = "Proceed with phase 1 (promote blog pages)? [y/N] "
        elif phase == 2:
            lines = format_taxonomy_migration_summary(get_taxonomy_migration_summary(config))
            prompt = "Proceed with phase 2 (create collections and themes)? [y/N] "
        elif phase == 3:
            lines = format_assign_taxonomies_summary(get_assign_taxonomies_summary(config))
            prompt = "Proceed with phase 3 (assign collections and themes to publications)? [y/N] "
        elif phase == 4:
            lines = []
            prompt = "Proceed with phase 4 (fix embedded links and blog_recent_entries blocks)? [y/N] "
        else:
            return

        self.stdout.write("")
        for line in lines:
            self._write_line(line, log_file)
        self.stdout.write("")

        answer = input(prompt)
        if log_file is not None:
            log_file.write(f"{prompt}{answer}\n")
            log_file.flush()
        if answer.strip().lower() not in {"y", "yes"}:
            raise CommandError("Migration aborted.")
