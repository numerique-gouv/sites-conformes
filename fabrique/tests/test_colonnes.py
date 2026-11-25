"""Largeur des colonnes des blocs « Colonnes multiples » et « Étapes » (gabarits surchargés dans
templates/content_manager/blocks/) : une colonne sous 768 px, et pas plus de deux par ligne de 768 à 992 px à
partir de 4 colonnes."""

from django.test import SimpleTestCase

from content_manager.blocks import MultiColumnsWithTitleBlock, StepperBlock


def colonnes_texte(n):
    return [{"type": "text", "value": f"<p>Colonne {i}</p>"} for i in range(n)]


class ColonnesMultiplesTest(SimpleTestCase):
    def rendu(self, colonnes):
        bloc = MultiColumnsWithTitleBlock()
        return bloc.render(bloc.to_python({"title": "Titre", "heading_tag": "h2", "columns": colonnes}))

    def test_trois_colonnes_cote_a_cote_des_la_tablette(self):
        html = self.rendu(colonnes_texte(3))
        self.assertEqual(html.count('class="fr-col-12 fr-col-md"'), 3)
        self.assertNotIn("fr-col-sm", html)

    def test_quatre_colonnes_deux_par_ligne_sur_tablette(self):
        html = self.rendu(colonnes_texte(4))
        self.assertEqual(html.count('class="fr-col-12 fr-col-md-6 fr-col-lg"'), 4)
        self.assertNotIn("fr-col-sm", html)

    def test_colonne_ajustable_garde_sa_largeur(self):
        html = self.rendu([{"type": "column", "value": {"width": "4", "content": colonnes_texte(1)}}])
        self.assertIn('class="fr-col-12 fr-col-lg-4"', html)


class EtapesTest(SimpleTestCase):
    def rendu(self, nombre):
        bloc = StepperBlock()
        etapes = [{"type": "step", "value": {"title": f"Étape {i}", "detail": "Détail"}} for i in range(nombre)]
        return bloc.render(
            bloc.to_python({"title": "Comment ça marche ?", "total": nombre, "current": 1, "steps": etapes})
        )

    def test_quatre_etapes_deux_par_ligne_sur_tablette(self):
        html = self.rendu(4)
        self.assertEqual(html.count('class="fr-col-12 fr-col-md-6 fr-col-lg"'), 4)
        self.assertNotIn("fr-col-sm", html)

    def test_trois_etapes_cote_a_cote_des_la_tablette(self):
        self.assertEqual(self.rendu(3).count('class="fr-col-12 fr-col-md"'), 3)
