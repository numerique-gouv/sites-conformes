from django.contrib.auth import get_user_model
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from blog.models import Organization
from numerique_gouv.models import MajorArea, Offertype, PageTag, TargetAudience

User = get_user_model()


class NumeriqueTestCase(WagtailPageTestCase):
    """
    Common setup for the numerique_gouv tests: home page, admin user and taxonomy snippets.
    """

    def setUp(self):
        self.home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")

        self.tag_ia = PageTag.objects.create(name="Intelligence artificielle", slug="ia")
        self.tag_data = PageTag.objects.create(name="Données", slug="donnees")
        self.tag_unused = PageTag.objects.create(name="Tag inutilisé", slug="tag-inutilise")

        self.area_cloud = MajorArea.objects.create(name="Cloud", slug="cloud")
        self.area_unused = MajorArea.objects.create(name="Axe inutilisé", slug="axe-inutilise")

        self.audience_agents = TargetAudience.objects.create(name="Agents publics", slug="agents_public")
        self.audience_citizens = TargetAudience.objects.create(name="Citoyens", slug="citoyens")
        self.audience_companies = TargetAudience.objects.create(name="Entreprises", slug="entreprises")

        self.dinum = Organization.objects.create(name="DINUM", slug="dinum")
        self.ans = Organization.objects.create(name="ANS", slug="ans")

        self.offer_types = {
            slug: Offertype.objects.create(name=slug.capitalize(), slug=slug)
            for slug in ["outil", "financement", "expertise", "pilotage", "observatoire", "document"]
        }

    def add_page(self, parent, page_class, **kwargs):
        kwargs.setdefault("owner", self.admin)
        page = parent.add_child(instance=page_class(**kwargs))
        page.save()
        return page
