import factory

from sites_conformes.blog.tests.factories import PublishedPageFactory
from sites_conformes.events.models import EventEntryPage, EventsIndexPage


class EventsIndexPageFactory(PublishedPageFactory):
    title = "Events index"
    slug = "events-index"

    class Meta:
        model = EventsIndexPage


class EventEntryPageFactory(PublishedPageFactory):
    title = factory.Sequence(lambda n: f"Event {n}")

    class Meta:
        model = EventEntryPage

    @factory.post_generation
    def categories(obj, create, extracted, **kwargs):
        if not create or not extracted:
            return
        for category in extracted:
            obj.categories.add(category)

    @factory.post_generation
    def tags(obj, create, extracted, **kwargs):
        if not create or not extracted:
            return
        for tag in extracted:
            obj.tags.add(tag)

    @factory.post_generation
    def authors(obj, create, extracted, **kwargs):
        if not create or not extracted:
            return
        for author in extracted:
            obj.authors.add(author)
