import swapper

# Name the swappable content page setting SF_CONTENTPAGE_MODEL rather than
# SITES_CONFORMES_CORE_CONTENTPAGE_MODEL, as Wagtail does for WAGTAIL_PAGE_MODEL.
# Done here so it applies before any model module is imported.
swapper.set_app_prefix("sites_conformes_core", "sf")
