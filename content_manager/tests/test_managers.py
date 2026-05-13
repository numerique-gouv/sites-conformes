from django.contrib.auth import get_user_model
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from sites_conformes.content_manager.models import ContentPage, Tag, TagContentPage

User = get_user_model()


class TagManagerTests(WagtailPageTestCase):
    def setUp(self):
        home_page = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.admin.save()
        lorem_body = []
        self.content_page_live = home_page.add_child(
            instance=ContentPage(title="Live page", slug="live-page", owner=self.admin, body=lorem_body, live=True)
        )
        self.content_page_live.save()

        self.another_live_page = home_page.add_child(
            instance=ContentPage(title="Another live", slug="another-live", owner=self.admin, body=[], live=True)
        )
        self.another_live_page.save()
        self.content_page_draft = home_page.add_child(
            instance=ContentPage(title="Draft page", slug="draft-page", owner=self.admin, body=lorem_body, live=False)
        )
        self.content_page_draft.save()
        self.tag = Tag.objects.create(name="Test tag")

        TagContentPage.objects.create(
            tag=self.tag,
            content_object=self.content_page_live,
        )
        TagContentPage.objects.create(
            tag=self.tag,
            content_object=self.content_page_draft,
        )

    def test_usecount_counts_only_live_pages(self):
        tag = Tag.objects.tags_with_usecount().get(pk=self.tag.pk)

        assert tag.usecount == 1

    def test_tag_with_only_draft_pages_has_zero_usecount(self):
        tag = Tag.objects.create(name="Draft only")

        TagContentPage.objects.create(
            tag=tag,
            content_object=self.content_page_draft,
        )

        tag = Tag.objects.tags_with_usecount().get(pk=tag.pk)

        assert tag.usecount == 0

    def test_usecount_multiple_live_pages(self):

        TagContentPage.objects.create(
            tag=self.tag,
            content_object=self.another_live_page,
        )

        tag = Tag.objects.tags_with_usecount().get(pk=self.tag.pk)
        assert tag.usecount == 2
