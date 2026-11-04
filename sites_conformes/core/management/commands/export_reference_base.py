import hashlib
import json
import subprocess  # nosec B404
from io import StringIO
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from wagtail.images import get_image_model
from wagtail.models import Collection, Page, Site, WorkflowPage, WorkflowTask

from sites_conformes.core.services.demo_sites import DEMO_DATA_DIR, DEMO_IMAGES_DIR, SITE_KEYS, load_demo_content

Image = get_image_model()

FIXTURES_DIR = DEMO_DATA_DIR / "fixtures"

# Objects that belong to several sites: they are recreated when loading these sites together
CROSS_SITE = "cross-site"

# Data that is rebuilt automatically, or specific to a machine or a session
EXCLUDED_MODELS = [
    "contenttypes",
    "auth.permission",
    "sessions",
    "admin.logentry",
    "wagtailcore.pagelogentry",
    "wagtailcore.modellogentry",
    "wagtailcore.referenceindex",
    "wagtailcore.uploadedfile",
    "wagtailadmin.editingsession",
    "wagtailsearch",
    "sites_conformes_customimages.customrendition",
    "sites_conformes_db_storage",
    "otp_static",
    "otp_totp",
]

# Where the images of the reference bases come from
IMAGE_SOURCE_DIRS = [
    DEMO_IMAGES_DIR,
    Path(settings.STATIC_ROOT) / "dsfr" / "dist" / "artwork" / "pictograms",
    Path(settings.STATIC_ROOT) / "illustration",
]


def get_installed_exclusions() -> list:
    installed_labels = {app_config.label for app_config in apps.get_app_configs()}
    return [excluded for excluded in EXCLUDED_MODELS if excluded.split(".")[0] in installed_labels]


def get_last_migrations() -> dict:
    """
    Returns the last migration of each app, which must all be applied.
    """
    loader = MigrationLoader(connection)
    leaf_nodes = sorted(loader.graph.leaf_nodes())
    unapplied = [node for node in leaf_nodes if node not in loader.applied_migrations]
    if unapplied:
        raise CommandError(f"Migrations non appliquées : {unapplied}. Lancez d'abord « migrate ».")
    return dict(leaf_nodes)


def dump_data() -> list:
    """
    Dumps the database with primary keys, as the natural keys of Wagtail collections and pages
    can't be loaded back. Only content types and permissions, whose ids depend on the database,
    are replaced by their natural keys.
    """
    output = StringIO()
    call_command("dumpdata", exclude=get_installed_exclusions(), stdout=output, verbosity=0)
    objects = json.loads(output.getvalue())

    natural_keys = {
        ContentType: {content_type.pk: list(content_type.natural_key()) for content_type in ContentType.objects.all()},
        Permission: {
            permission.pk: list(permission.natural_key())
            for permission in Permission.objects.select_related("content_type")
        },
    }

    for obj in objects:
        model = apps.get_model(obj["model"])
        for model_field in model._meta.get_fields():
            keys = natural_keys.get(model_field.related_model)
            value = obj["fields"].get(model_field.name)
            if not keys or value is None or not model_field.concrete:
                continue
            if model_field.many_to_many:
                obj["fields"][model_field.name] = [keys[pk] for pk in value]
            else:
                obj["fields"][model_field.name] = keys[value]

    return objects


def get_root_model(model):
    """
    Pages and tasks are stored in several tables (multi-table inheritance), with the same primary key.
    """
    parents = model._meta.get_parent_list()
    return parents[-1] if parents else model


def object_key(model, pk) -> tuple:
    return (get_root_model(model)._meta.label_lower, str(pk))


def get_site_seeds() -> dict:
    """
    Returns, for each demo site, the keys of the objects that obviously belong to it.
    """
    site_names = {spec["key"]: spec["site_name"] for spec in load_demo_content()["sites"]}
    seeds = {}

    for site in Site.objects.all():
        site_key = next((key for key, name in site_names.items() if name == site.site_name), None)
        if not site_key:
            raise CommandError(f"Le site {site.site_name} n'est pas un site de démo.")

        homes = [site.root_page, *site.root_page.get_translations()]
        pages = Page.objects.none()
        for home in homes:
            pages |= Page.objects.descendant_of(home, inclusive=True)
        groups = Group.objects.filter(page_permissions__page__in=homes).distinct()
        workflows = WorkflowPage.objects.filter(page__in=homes).values_list("workflow_id", flat=True)
        tasks = WorkflowTask.objects.filter(workflow_id__in=workflows).values_list("task_id", flat=True)

        keys = {object_key(Site, site.pk)}
        keys |= {object_key(Page, pk) for pk in pages.values_list("pk", flat=True)}
        collections = Collection.objects.filter(name=site.site_name).values_list("pk", flat=True)
        keys |= {object_key(Collection, pk) for pk in collections}
        keys |= {object_key(Group, pk) for pk in groups.values_list("pk", flat=True)}
        keys |= {object_key(WorkflowPage._meta.get_field("workflow").related_model, pk) for pk in workflows}
        keys |= {object_key(WorkflowTask._meta.get_field("task").related_model, pk) for pk in tasks}
        seeds[site_key] = keys

    return seeds


def get_references(obj: dict, natural_models: dict) -> set:
    """
    Returns the keys of the objects referenced by a serialized object.
    """
    model = apps.get_model(obj["model"])
    fields = obj["fields"]
    references = set()

    # Forward relations only: many-to-many fields are not "concrete", as they have no column
    for model_field in [*model._meta.fields, *model._meta.many_to_many]:
        related_model = model_field.related_model
        value = fields.get(model_field.name)
        if related_model is None or value is None:
            continue
        if related_model in (ContentType, Permission):
            continue
        values = value if model_field.many_to_many else [value]
        references |= {object_key(related_model, pk) for pk in values}

    # Generic relations (revisions, tags)
    content_type = fields.get("base_content_type") or fields.get("content_type")
    if content_type and fields.get("object_id") is not None:
        related_model = natural_models[tuple(content_type)]
        references.add(object_key(related_model, fields["object_id"]))

    return references


def split_by_site(objects: list) -> dict:
    """
    Returns the owner of each serialized object: a site key, CROSS_SITE, or None when shared.
    An object belongs to a site when it is one of its seeds, or references an object of this site.
    """
    natural_models = {
        tuple(content_type.natural_key()): content_type.model_class() for content_type in ContentType.objects.all()
    }
    owners = {key: site_key for site_key, keys in get_site_seeds().items() for key in keys}
    references = {
        object_key(apps.get_model(obj["model"]), obj["pk"]): get_references(obj, natural_models) for obj in objects
    }

    changed = True
    while changed:
        changed = False
        for key, refs in references.items():
            if key in owners:
                continue
            ref_owners = {owners[ref] for ref in refs if owners.get(ref)}
            if len(ref_owners) == 1:
                owners[key] = ref_owners.pop()
                changed = True
            elif len(ref_owners) > 1:
                owners[key] = CROSS_SITE
                changed = True

    # Each fixture is loaded alone in monosite: it must only reference its own or shared objects
    errors = []
    for key, refs in references.items():
        owner = owners.get(key)
        if owner == CROSS_SITE and key[0] != get_root_model(get_user_model())._meta.label_lower:
            errors.append(f"{key} appartient à plusieurs sites")
        elif owner not in (None, CROSS_SITE):
            foreign = sorted(ref for ref in refs if owners.get(ref) not in (None, owner))
            if foreign:
                errors.append(f"{key} (site {owner}) référence {foreign}")
    if errors:
        raise CommandError("Ces objets empêchent de séparer les sites :\n" + "\n".join(errors))

    return {key: owners.get(key) for key in references}


def get_commit() -> str:
    """
    The fixture can only be loaded with the models of this commit.
    """
    try:
        result = subprocess.run(  # nosec B603 B607 -- developer-run-only CLI tool, fixed arguments
            ["git", "rev-parse", "HEAD"], cwd=settings.BASE_DIR, capture_output=True, text=True
        )
    except OSError:
        return ""
    return result.stdout.strip()


def hash_file(path: Path) -> str:
    # Same hash as the file_hash of Wagtail images
    return hashlib.sha1(path.read_bytes(), usedforsecurity=False).hexdigest()  # NOSONAR


def get_image_sources() -> dict:
    """
    Maps the file of each image to the file of the repository it was imported from.
    """
    sources_by_hash = {}
    for source_dir in IMAGE_SOURCE_DIRS:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file() and path.suffix != ".md":
                sources_by_hash.setdefault(hash_file(path), str(path.relative_to(settings.BASE_DIR)))

    result = {}
    for image in Image.objects.order_by("pk"):
        image_hash = image.file_hash or hashlib.sha1(image.file.read(), usedforsecurity=False).hexdigest()  # NOSONAR
        result[image.file.name] = sources_by_hash.get(image_hash)
    return result


class Command(BaseCommand):
    help = """
    Exports the demo sites as reference bases, with one fixture and one manifest per site,
    to be loaded later with load_reference_base.
    Run it on a database created by setup_multisite_demo, with both sites.
    """

    def handle(self, *args, **kwargs):
        FIXTURES_DIR.mkdir(exist_ok=True)

        image_sources = get_image_sources()
        missing = [file_name for file_name, source in image_sources.items() if not source]
        if missing:
            self.stdout.write(self.style.WARNING(f"Images sans fichier source dans le dépôt : {', '.join(missing)}"))

        objects = dump_data()
        owners = split_by_site(objects)
        commit = get_commit()
        migrations = get_last_migrations()

        for site_key in SITE_KEYS:
            # Shared objects are written identically in each fixture
            site_objects = [
                obj
                for obj in objects
                if owners[object_key(apps.get_model(obj["model"]), obj["pk"])] in (None, site_key)
            ]
            image_label = Image._meta.label_lower
            images = [obj["fields"]["file"] for obj in site_objects if obj["model"] == image_label]

            fixture_path = FIXTURES_DIR / f"site-{site_key}.json"
            with open(fixture_path, "w", encoding="utf-8") as fixture_file:
                json.dump(site_objects, fixture_file, indent=1, ensure_ascii=False)
                fixture_file.write("\n")

            manifest = {
                "commit": commit,
                "migrations": migrations,
                "images": {file_name: image_sources.get(file_name) for file_name in images},
            }
            manifest_path = FIXTURES_DIR / f"site-{site_key}.manifest.json"
            with open(manifest_path, "w", encoding="utf-8") as manifest_file:
                json.dump(manifest, manifest_file, indent=1, ensure_ascii=False)
                manifest_file.write("\n")

            self.stdout.write(self.style.SUCCESS(f"Site {site_key} exporté : {fixture_path} et {manifest_path}"))
