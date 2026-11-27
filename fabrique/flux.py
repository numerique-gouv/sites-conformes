"""Flux iCal d'abonnement à l'agenda de la Fabrique.

Deux flux, à ajouter à son agenda (Outlook, Apple, Google…) par abonnement : l'agenda se met ensuite à jour
tout seul, au rythme choisi par son logiciel (en général quelques heures).

- /flux/agenda-fabrique.ics : l'essentiel. Tous les événements de la Fabrique de la donnée territoriale, et
  seulement les comités des équipes produits (types ou étiquettes commençant par « Comité »). Un événement saisi à
  la main dans Wagtail, sans étiquettes Grist, est considéré comme un événement de la Fabrique.
- /flux/agenda-complet.ics : tous les événements de l'agenda.

Contrairement à l'export iCal de Sites Faciles (événements à venir seulement), les flux gardent les événements des
trois derniers mois : un agenda abonné ne voit pas disparaître une réunion le lendemain.
"""

import os
from datetime import timedelta

from django.http import Http404, HttpResponse
from django.utils import timezone
from icalendar import Calendar, Event, vText
from wagtail.models import Site

from events.models import EventEntryPage, EventsIndexPage

FABRIQUE = "Fabrique de la donnée territoriale"
HISTORIQUE = timedelta(days=90)
FLUX = {
    "agenda-fabrique": "l'essentiel (Fabrique et comités des équipes)",
    "agenda-complet": "tous les événements",
}


def essentiel(page) -> bool:
    """Événement de la Fabrique, ou comité d'une équipe."""
    etiquettes = getattr(page, "etiquettes_grist", None)
    if etiquettes is None:
        return True  # saisi à la main dans Wagtail
    if FABRIQUE in (etiquettes.equipes or []):
        return True
    noms = [etiquettes.type or ""] + [tag.name for tag in page.tags.all()]
    return any(nom.casefold().startswith("comité") for nom in noms)


def index_agenda(request) -> EventsIndexPage:
    site = Site.find_for_request(request) or Site.objects.get(is_default_site=True)
    slug = os.getenv("FABRIQUE_AGENDA_SLUG", "agenda")
    index = EventsIndexPage.objects.child_of(site.root_page).filter(slug=slug).live().first()
    if index is None:
        raise Http404("Agenda introuvable")
    return index


def evenement_ical(page, request, dtstamp) -> Event:
    event = Event()
    annule = page.title.startswith("Annulé : ")
    event.add("summary", page.title)
    event.add("dtstart", page.event_date_start)
    event.add("dtend", page.event_date_end or page.event_date_start)
    event.add("dtstamp", dtstamp)
    event.add("uid", f"evenement-{page.pk}@{request.get_host()}")
    if page.location:
        event["location"] = vText(page.location)
    url = page.get_full_url(request)
    event.add("url", url)
    description = "\n\n".join(p for p in (page.search_description or "", url) if p)
    event.add("description", description)
    if annule:
        event.add("status", "CANCELLED")
    return event


def flux_agenda(request, nom: str) -> HttpResponse:
    if nom not in FLUX:
        raise Http404("Flux inconnu")
    index = index_agenda(request)
    pages = (
        EventEntryPage.objects.descendant_of(index)
        .live()
        .filter(event_date_end__gte=timezone.now() - HISTORIQUE)
        .order_by("event_date_start", "pk")
        .select_related("etiquettes_grist")
        .prefetch_related("tags")
    )
    if nom == "agenda-fabrique":
        pages = [p for p in pages if essentiel(p)]

    titre = "Agenda de la Fabrique de la donnée territoriale"
    if nom == "agenda-complet":
        titre += " (complet)"
    cal = Calendar()
    cal.add("prodid", "-//Fabrique de la donnée territoriale//Agenda//FR")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", titre)
    cal.add("x-wr-caldesc", f"Événements de la Fabrique de la donnée territoriale : {FLUX[nom]}.")
    cal.add("x-wr-timezone", "Europe/Paris")
    # Indication de rafraîchissement (respectée par certains logiciels, dont Apple Calendrier).
    cal.add("refresh-interval", timedelta(hours=4), parameters={"VALUE": "DURATION"})
    cal.add("x-published-ttl", "PT4H")
    dtstamp = timezone.now()
    for page in pages:
        cal.add_component(evenement_ical(page, request, dtstamp))

    reponse = HttpResponse(cal.to_ical(), content_type="text/calendar; charset=utf-8")
    reponse["Content-Disposition"] = f'inline; filename="{nom}.ics"'
    reponse["Cache-Control"] = "public, max-age=900"
    return reponse
