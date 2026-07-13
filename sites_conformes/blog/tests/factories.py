import zoneinfo
from datetime import datetime

import factory
import wagtail_factories
from django.utils.text import slugify

from sites_conformes.blog.models import BlogEntryPage, BlogIndexPage, Category, Organization, Person
from sites_conformes.core.models import Tag

PARIS_TZ = zoneinfo.ZoneInfo("Europe/Paris")
DEFAULT_POST_DATE = datetime(2024, 1, 1, 12, 0, 0, tzinfo=PARIS_TZ)


class PublishedPageFactory(wagtail_factories.PageFactory):
    # ``publish`` is a post_generation hook: it runs after the page is created in the
    # tree. Pass ``publish=False`` to skip (e.g. when testing unsaved defaults).
    @factory.post_generation
    def publish(obj, create, extracted, **kwargs):
        if create and extracted is not False:
            obj.save_revision().publish()


class BlogIndexPageFactory(PublishedPageFactory):
    title = "Blog index"
    slug = "blog-index"

    class Meta:
        model = BlogIndexPage


class BlogEntryPageFactory(PublishedPageFactory):
    title = factory.Sequence(lambda n: f"Blog post {n}")
    date = DEFAULT_POST_DATE

    class Meta:
        model = BlogEntryPage

    @factory.post_generation
    def blog_categories(obj, create, extracted, **kwargs):
        if not create or not extracted:
            return
        for category in extracted:
            obj.blog_categories.add(category)

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


class TagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tag

    name = factory.Sequence(lambda n: f"Tag {n}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.name))


class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Organization {n}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.name))


class PersonFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Person

    name = factory.Sequence(lambda n: f"Person {n}")
    role = "Writer"
    organization = factory.SubFactory(OrganizationFactory)


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.name))
