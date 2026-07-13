import factory
from django.utils.text import slugify

from publications.models import Collection, PublicationIndexPage, PublicationPage, Theme
from sites_conformes.blog.tests.factories import DEFAULT_POST_DATE, PublishedPageFactory


class PublicationIndexPageFactory(PublishedPageFactory):
    title = "Publications index"
    slug = "publications-index"

    class Meta:
        model = PublicationIndexPage


class PublicationPageFactory(PublishedPageFactory):
    title = factory.Sequence(lambda n: f"Post {n}")
    date = DEFAULT_POST_DATE

    class Meta:
        model = PublicationPage

    @factory.post_generation
    def collections(obj, create, extracted, **kwargs):
        if not create or not extracted:
            return
        for collection in extracted:
            obj.collections.add(collection)

    @factory.post_generation
    def themes(obj, create, extracted, **kwargs):
        if not create or not extracted:
            return
        for theme in extracted:
            obj.themes.add(theme)

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


class CollectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Collection

    name = factory.Sequence(lambda n: f"Collection {n}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.name))


class ThemeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Theme

    name = factory.Sequence(lambda n: f"Theme {n}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.name))
