from sites_conformes.blog.tests import test_blog_index_page as blog_tests
from sites_conformes.events.models import EventsIndexPage
from sites_conformes.events.tests.factories import EventEntryPageFactory, EventsIndexPageFactory


class EventsIndexPageMixin:
    index_page_class = EventsIndexPage
    index_page_factory = EventsIndexPageFactory
    entry_page_factory = EventEntryPageFactory


class EventsIndexPageSettingsTest(EventsIndexPageMixin, blog_tests.BlogIndexPageSettingsTest):
    pass


class EventsIndexPageFilterQueryTest(EventsIndexPageMixin, blog_tests.BlogIndexPageFilterQueryTest):
    pass


class EventsIndexPagePostsTest(EventsIndexPageMixin, blog_tests.BlogIndexPagePostsTest):
    pass
