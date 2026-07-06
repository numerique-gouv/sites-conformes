from django.utils.translation import gettext_lazy as _

from sites_conformes.blog.models import Category
from sites_conformes.blog.taxonomy import Taxonomy

CATEGORY = Taxonomy(
    slug="category",
    model=Category,
    m2m_field="blog_categories",
    filter_field="filter_by_category",
    filter_heading=_("Filter by category"),
    list_label_plural=_("Categories"),
    list_route_name="categories_list",
    list_template="sites_conformes_blog/categories_list_page.html",
    list_prefix="cat",
    list_context_key="categories",
    current_context_key="current_category",
    filtered_title=_("Posts in category %(category)s"),
    filtered_title_param="category",
)
