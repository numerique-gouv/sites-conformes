import requests
from django.contrib.admin.utils import quote
from django.core.cache import cache
from django.urls import reverse
from wagtail.admin.admin_url_finder import AdminURLFinder
from wagtail.admin.ui.components import Component
from wagtail.models import Site

finder = AdminURLFinder()


class ShortcutsPanel(Component):
    order = 50

    def get_context_data(self, parent_content=None):
        site = Site.objects.filter(is_default_site=True).first()
        home_page = site.root_page
        home_page_edit = reverse("wagtailadmin_pages:edit", args=(quote(home_page.pk),))
        pages_list = reverse("wagtailadmin_explore", args=(quote(home_page.pk),))
        create_page_url = reverse("wagtailadmin_pages:add_subpage", args=(home_page.pk,))
        settings_url = reverse("wagtailsettings:edit", args=["content_manager", "cmsdsfrconfig", site.pk])
        main_menus_url = reverse("wagtailsnippets_menus_mainmenu:list")

        return {
            "site": site,
            "home_page_edit": home_page_edit,
            "pages_list": pages_list,
            "create_page": create_page_url,
            "settings_url": settings_url,
            "main_menus": main_menus_url,
        }

    template_name = "wagtailadmin/home/panels/_main_links.html"


shortcuts_panel = ShortcutsPanel()


class TutorialsPanel(Component):
    order = 300
    TUTORIAL_PANEL_CACHE_KEY = "tutorials_panel"
    TUTORIAL_PANEL_CACHE_TIMEOUT = 60 * 60 * 24 * 7  # Cache for one week

    def get_context_data(self, parent_content=None):
        tutorials = cache.get(self.TUTORIAL_PANEL_CACHE_KEY)

        if tutorials is None:
            try:
                res = requests.get(
                    "https://sites.beta.gouv.fr/api/v2/pages/",
                    params={
                        "child_of": 107,
                    },
                    timeout=5,
                )
                res.raise_for_status()
                tutorials = []
                for page in res.json()["items"]:
                    page_res = requests.get(
                        f'https://sites.beta.gouv.fr/api/v2/pages/{page["id"]}/',
                        params={"fields": "title,preview_image_render,-body"},
                        timeout=5,
                    )
                    page_res.raise_for_status()
                    page_data = page_res.json()
                    tutorials.append(
                        {
                            "title": page_data["title"],
                            "image": page_data["preview_image_render"]["full_url"],
                            "url": page_data["meta"]["html_url"],
                        }
                    )
            except requests.RequestException:
                tutorials = []

            cache.set(self.TUTORIAL_PANEL_CACHE_KEY, tutorials, self.TUTORIAL_PANEL_CACHE_TIMEOUT)
        return {"tutorials": tutorials}

    template_name = "wagtailadmin/home/panels/_tutorials.html"


tutorials_panel = TutorialsPanel()
