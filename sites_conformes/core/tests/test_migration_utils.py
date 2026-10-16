from django.apps import apps
from django.contrib.auth import get_user_model
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.core.migration_utils import rename_revision_field
from sites_conformes.core.models import CatalogIndexPage


class RenameRevisionFieldTestCase(WagtailPageTestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser("test", "test@test.test", "pass")
        self.page = Page.objects.get(slug="home").add_child(
            instance=CatalogIndexPage(title="Catalogue", slug="catalogue", owner=admin)
        )
        self.page.posts_per_page = 7
        self.revision = self.page.save_revision()
        # A draft saved before the field was renamed.
        self.revision.content["entries_per_page"] = self.revision.content.pop("posts_per_page")
        self.revision.save()
        self.forward, self.backward = rename_revision_field(
            "sites_conformes_core", "CatalogIndexPage", "entries_per_page", "posts_per_page"
        )

    def test_a_draft_keeps_the_value_of_a_renamed_field(self):
        self.forward(apps, None)

        self.revision.refresh_from_db()
        self.assertEqual(self.revision.as_object().posts_per_page, 7)
        self.assertNotIn("entries_per_page", self.revision.content)

    def test_the_rename_can_be_reverted(self):
        self.forward(apps, None)
        self.backward(apps, None)

        self.revision.refresh_from_db()
        self.assertEqual(self.revision.content["entries_per_page"], 7)
