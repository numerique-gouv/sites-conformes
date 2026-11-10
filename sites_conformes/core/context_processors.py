def skiplinks(request) -> dict:
    return {
        "skiplinks": [
            {"link": "#content", "label": "Contenu"},
            {"link": "#fr-navigation", "label": "Menu"},
        ]
    }


def mega_menus(request) -> dict:
    # Deprecated: the legacy mega menus have been removed. Kept as a no-op so that host projects
    # still listing it in their settings don't break. To be removed along with wagtailmenus.
    return {"mega_menus": []}


def iframe(request) -> dict:
    return {"iframe": getattr(request, "iframe", False)}
