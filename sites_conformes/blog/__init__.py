import swapper

# Name the swappable blog entry setting SF_BLOGENTRYPAGE_MODEL, like SF_CONTENTPAGE_MODEL.
# Done here so it applies before any model module is imported.
swapper.set_app_prefix("sites_conformes_blog", "sf")
