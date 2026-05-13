from django.core.management import call_command
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.content_manager.models import ContentPage


class ImportPagesTestCase(WagtailPageTestCase):
    def setUp(self):
        call_command("create_starter_pages")
        call_command("import_page_templates")
        self.templates_index = ContentPage.objects.get(slug="page_templates_index")
        self.home_page = ContentPage.objects.get(slug="home")

    def test_copied_template_is_correctly_updated(self):
        template = ContentPage.objects.child_of(self.templates_index).first()
        new_page = template.copy(to=self.home_page)

        self.assertEqual(new_page.get_parent(), self.home_page)
        self.assertEqual(new_page.source_url, None)

        find_template = (
            ContentPage.objects.child_of(self.templates_index).filter(source_url=template.source_url).first()
        )
        self.assertEqual(template.id, find_template.id)
