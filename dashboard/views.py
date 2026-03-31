import json

import requests
from django.contrib.admin.utils import quote
from django.urls import reverse
from wagtail.admin.admin_url_finder import AdminURLFinder
from wagtail.admin.ui.components import Component
from wagtail.models import Site

from .utils import get_all_notifications

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

    def get_context_data(self, parent_content=None):

        try:
            res = requests.get(
                "https://sites.beta.gouv.fr/api/v2/pages/?child_of=107",
                timeout=30,
            )
            res.raise_for_status()
            data = res.json()
            tutorial_pages = [{"id": page["id"]} for page in data["items"]]
            tutorials = []
            for page_id in tutorial_pages:
                page = json.loads(
                    requests.get(
                        f'https://sites.beta.gouv.fr/api/v2/pages/{page_id["id"]}/?fields=title,preview_image_render,-body'
                    ).text
                )
                tutorials.append(
                    {
                        "title": page["title"],
                        "image": page["preview_image_render"]["full_url"],
                        "url": page["meta"]["html_url"],
                    }
                )
        except requests.RequestException:
            tutorials = []

        return {"tutorials": tutorials}

    template_name = "wagtailadmin/home/panels/_tutorials.html"


tutorials_panel = TutorialsPanel()


INFORMATION_URL = "https://raw.githubusercontent.com/Luzzzi/test-information-panel/main/test.json"
# INFORMATION_CACHE_KEY = "sf_information_panel"
# INFORMATION_CACHE_TIMEOUT = 60 * 60
LATEST_RELEASE_URL = "https://api.github.com/repos/numerique-gouv/sites-faciles/releases/latest"


class InformationPanel(Component):
    order = 20
    template_name = "wagtailadmin/home/panels/_information.html"
    panel_id = "information"

    def get_context_data(self, parent_context=None):
        items = get_all_notifications()

        return {"information_items": items}
