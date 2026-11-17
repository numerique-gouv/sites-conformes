from django.core.management.base import BaseCommand
from wagtail.images import get_image_model


class Command(BaseCommand):
    help = """
    Debug tool to benchmark warm_renditions: delete the renditions converted to WebP
    by the {% picture %} tag, back to their state right after deploying it.
    Renditions have no creation date, the WebP format is what tells them apart.
    """

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Count the renditions without deleting them.")

    def handle(self, *args, **options):
        renditions = get_image_model().get_rendition_model().objects.filter(filter_spec__contains="format-webp")
        if options["dry_run"]:
            self.stdout.write(f"{renditions.count()} renditions would be deleted")
            return
        # Deleting through the ORM also deletes the files and purges the renditions cache (Wagtail signals)
        deleted, _ = renditions.delete()
        self.stdout.write(f"{deleted} renditions deleted")
