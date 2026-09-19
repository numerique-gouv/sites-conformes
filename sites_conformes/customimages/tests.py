from importlib import import_module

from django.apps import apps
from django.test import TestCase
from wagtail.images import get_image_model
from wagtail.images.models import Image as WagtailImage
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Collection

CustomImage = get_image_model()

# La migration a un nom qui commence par un chiffre : on l'importe via import_module.
copy_migration = import_module("sites_conformes.customimages.migrations.0002_copy_wagtail_images")


class CopyWagtailImagesTest(TestCase):
    """Tests de la migration de copie des images Wagtail vers CustomImage (commande #419)."""

    def _make_collection(self):
        return Collection.objects.first() or Collection.add_root(name="Root")

    def test_copy_preserves_all_fields_and_tags(self):
        collection = self._make_collection()
        old = WagtailImage.objects.create(
            title="Photo",
            file=get_test_image_file(),
            focal_point_x=10,
            focal_point_y=20,
            focal_point_width=30,
            focal_point_height=40,
            collection=collection,
        )
        old.tags.add("alpha", "beta")
        old.refresh_from_db()

        copy_migration.copy_images(apps, None)

        new = CustomImage.objects.get(id=old.id)
        self.assertEqual(new.title, old.title)
        self.assertEqual(new.width, old.width)
        self.assertEqual(new.height, old.height)
        # Champs qui étaient perdus avant la correction de Fabien
        self.assertEqual(new.focal_point_x, 10)
        self.assertEqual(new.focal_point_y, 20)
        self.assertEqual(new.focal_point_width, 30)
        self.assertEqual(new.focal_point_height, 40)
        self.assertEqual(new.collection_id, old.collection_id)
        self.assertEqual(new.file_size, old.file_size)
        self.assertEqual(new.file_hash, old.file_hash)
        self.assertEqual(set(new.tags.names()), {"alpha", "beta"})

    def test_copy_is_idempotent(self):
        old = WagtailImage.objects.create(title="Photo", file=get_test_image_file())

        copy_migration.copy_images(apps, None)
        copy_migration.copy_images(apps, None)

        self.assertEqual(CustomImage.objects.filter(id=old.id).count(), 1)

    def test_reverse_removes_copied_images_and_tags(self):
        old = WagtailImage.objects.create(title="Photo", file=get_test_image_file())
        old.tags.add("gamma")

        copy_migration.copy_images(apps, None)
        new = CustomImage.objects.get(id=old.id)
        self.assertEqual(set(new.tags.names()), {"gamma"})

        copy_migration.reverse_copy_images(apps, None)

        self.assertFalse(CustomImage.objects.filter(id=old.id).exists())
