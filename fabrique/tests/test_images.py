from types import SimpleNamespace

from django.test import SimpleTestCase

from fabrique.templatetags.fabrique_images import largeur_vignette


def image(largeur, hauteur):
    return SimpleNamespace(width=largeur, height=hauteur)


class LargeurVignetteTests(SimpleTestCase):
    def test_meme_surface_quel_que_soit_le_format(self):
        self.assertEqual(largeur_vignette(image(1600, 900)), 240)  # 240 × 135
        self.assertEqual(largeur_vignette(image(300, 100)), 312)  # 312 × 104
        self.assertEqual(largeur_vignette(image(800, 200)), 360)  # 360 × 90

    def test_hauteur_plafonnee(self):
        # Carré ou portrait : pas plus haut que 144 px.
        self.assertEqual(largeur_vignette(image(500, 500)), 144)
        self.assertEqual(largeur_vignette(image(300, 400)), 108)

    def test_petite_image_agrandie(self):
        # Un logo de 120 × 60 est affiché comme un grand logo au même format.
        self.assertEqual(largeur_vignette(image(120, 60)), largeur_vignette(image(1200, 600)))

    def test_sans_dimensions(self):
        self.assertEqual(largeur_vignette(image(0, 0)), 0)
        self.assertEqual(largeur_vignette(None), 0)
