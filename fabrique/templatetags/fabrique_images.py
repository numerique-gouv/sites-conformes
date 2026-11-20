"""Balises de gabarit de la Fabrique pour les images."""

import math

from django import template

register = template.Library()

# Surface visée pour les vignettes de l'agenda (px²) : environ 240 × 135 pour une image 16:9.
SURFACE_VIGNETTE = 240 * 135
# Hauteur maximale d'une vignette (px), comme max-height dans fabrique/static/fabrique/agenda.css (9rem).
HAUTEUR_MAX_VIGNETTE = 144


@register.filter
def largeur_vignette(image) -> int:
    """Largeur d'affichage (px) d'une vignette pour que toutes aient à peu près la même surface.

    À hauteur maximale égale, un logo carré paraît bien plus petit qu'un logo en longueur, et une image
    de petite taille n'est pas agrandie : on fixe la largeur d'après le rapport largeur/hauteur pour une
    surface constante, sans dépasser la hauteur maximale. La largeur de la carte reste une limite (CSS).
    """
    largeur, hauteur = getattr(image, "width", 0), getattr(image, "height", 0)
    if not largeur or not hauteur:
        return 0
    rapport = largeur / hauteur
    return round(min(math.sqrt(SURFACE_VIGNETTE * rapport), HAUTEUR_MAX_VIGNETTE * rapport))
