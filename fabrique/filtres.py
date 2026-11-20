"""Étiquettes de filtre de la page Agenda, rangées par sorte : équipe, type d'événement, série.

Sites Faciles affiche toutes les étiquettes des événements en une seule liste. Celles des événements venus de Grist
mêlent le type (Webinaire…), les équipes (RNB…) et les séries (Collectif vigie…). On les reconnaît grâce aux
étiquettes Grist gardées pour chaque événement (fabrique.EtiquettesEvenement) : une étiquette qui est une équipe d'un
événement de l'agenda va dans « Par équipe », un type dans « Par type d'événement », le reste dans « Par série ».
"""

from dataclasses import dataclass, field

from fabrique.calendrier import EQUIPES
from fabrique.models import EtiquettesEvenement

# Couleur DSFR des étiquettes d'équipe, la même que dans le calendrier (fabrique/static/fabrique/agenda.css).
COULEURS_TAGS = {
    "panoramax": "fr-tag--purple-glycine",
    "rnb": "fr-tag--green-emeraude",
    "ban": "fr-tag--yellow-tournesol",
    "voies-locales": "fr-tag--pink-tuile",
    "fabrique": "",  # bleu France, la couleur par défaut des étiquettes
}
# Même couleur que l'étiquette de type sur les cartes de la liste (classe fabrique-tag-type).
CLASSE_TYPE = "fr-tag--blue-ecume"


@dataclass
class Groupe:
    titre: str
    etiquettes: list = field(default_factory=list)  # [(tag, classe CSS), …]


def grouper(tags, index) -> list[Groupe]:
    """Groupes non vides, dans l'ordre : équipes, types, séries. Les étiquettes gardent l'ordre reçu (alphabétique)."""
    etiquettes = EtiquettesEvenement.objects.filter(page__path__startswith=index.path)
    types, equipes = set(), set()
    for e in etiquettes:
        if e.type:
            types.add(e.type.casefold())
        equipes.update(nom.casefold() for nom in e.equipes or [])
    couleurs = {nom.casefold(): COULEURS_TAGS.get(couleur, "") for nom, couleur in EQUIPES}

    par_equipe = Groupe("Par équipe")
    par_type = Groupe("Par type d'événement")
    par_serie = Groupe("Par série")
    for tag in tags:
        nom = tag.name.casefold()
        if nom in equipes:
            par_equipe.etiquettes.append((tag, couleurs.get(nom, "")))
        elif nom in types:
            par_type.etiquettes.append((tag, CLASSE_TYPE))
        else:
            par_serie.etiquettes.append((tag, ""))
    return [g for g in (par_equipe, par_type, par_serie) if g.etiquettes]
