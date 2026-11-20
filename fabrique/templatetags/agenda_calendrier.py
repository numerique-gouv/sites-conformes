"""Balises de la vue calendrier de l'agenda (voir fabrique/calendrier.py)."""

from django import template

from events.models import EventsIndexPage
from fabrique import calendrier

register = template.Library()


@register.simple_tag(takes_context=True)
def vue_agenda(context) -> str:
    """« calendrier » (par défaut) ou « liste » sur la page Agenda ; vide ailleurs (archives…)."""
    request, page = context.get("request"), context.get("page")
    if request is None or not isinstance(getattr(page, "specific", page), EventsIndexPage):
        return ""
    if request.path != page.url:  # sous-page routée : archives, iCal…
        return ""
    return "liste" if request.GET.get("vue") == "liste" else "calendrier"


@register.inclusion_tag("fabrique/agenda/bascule.html", takes_context=True)
def bascule_agenda(context, vue: str) -> dict:
    request = context["request"]
    return {
        "vue": vue,
        "url_calendrier": calendrier.url_avec(request, vue=None, date_from=None, date_to=None),
        "url_liste": calendrier.url_avec(request, vue="liste", mois=None),
    }


@register.inclusion_tag("fabrique/agenda/calendrier.html", takes_context=True)
def calendrier_agenda(context) -> dict:
    return calendrier.construire(context["page"], context["request"])


@register.inclusion_tag("fabrique/agenda/filtres_etiquettes.html", takes_context=True)
def filtres_etiquettes_agenda(context) -> dict:
    """Filtre par étiquette de la page Agenda, en trois groupes (voir fabrique/filtres.py)."""
    from fabrique.filtres import grouper

    return {
        "groupes": grouper(context.get("tags") or [], context["page"]),
        "page": context["page"],
        "request": context["request"],
        "current_tag": context.get("current_tag"),
    }
