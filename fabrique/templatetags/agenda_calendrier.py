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


@register.simple_tag(takes_context=True)
def posts_agenda(context):
    """Événements de la liste de la page Agenda.

    Sites Faciles n'y met que les événements à venir, puis applique le filtre par date : une date passée ne donnait
    donc aucun résultat (et les archives ne filtrent que par année). Quand le filtre par date remonte dans le passé,
    on reprend tous les événements de la période, passés compris, avec les mêmes filtres d'étiquette et de
    catégorie. Sinon, la liste de Sites Faciles est gardée telle quelle."""
    from datetime import date

    from django.core.paginator import Paginator
    from django.utils import timezone

    from events.models import EventEntryPage

    posts, request, page = context.get("posts"), context.get("request"), context.get("page")
    if request is None or page is None:
        return posts
    try:
        debut = date.fromisoformat(request.GET["date_from"]) if request.GET.get("date_from") else None
        fin = date.fromisoformat(request.GET["date_to"]) if request.GET.get("date_to") else None
    except ValueError:
        return posts
    aujourdhui = timezone.localdate()
    if not ((debut and debut < aujourdhui) or (fin and fin < aujourdhui)):
        return posts
    if request.GET.get("source") or request.GET.get("author"):  # filtres non repris ici, rares dans l'agenda
        return posts

    evenements = EventEntryPage.objects.descendant_of(page).live()
    if debut:
        evenements = evenements.filter(event_date_end__date__gte=debut)
    if fin:
        evenements = evenements.filter(event_date_start__date__lte=fin)
    if request.GET.get("tag"):
        evenements = evenements.filter(tags__slug=request.GET["tag"])
    if request.GET.get("category"):
        evenements = evenements.filter(event_categories__slug=request.GET["category"])
    evenements = (
        evenements.distinct()
        .order_by("event_date_start", "pk")
        .select_related("etiquettes_grist")
        .prefetch_related("tags", "event_categories")
    )
    return Paginator(evenements, page.posts_per_page).get_page(request.GET.get("page"))
