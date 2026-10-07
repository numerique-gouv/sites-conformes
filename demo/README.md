# Demo sites-conformes

Projet Django/Wagtail minimal qui consomme le package [`sites-conformes`](https://pypi.org/project/sites-conformes/)
pour montrer comment l’intégrer dans un site existant. Pas destiné à être déployé.

## Ce qu’il y a dedans

| Dossier      | Rôle                                                                                    |
| ------------ | --------------------------------------------------------------------------------------- |
| `demo/`      | Configuration Django (settings, urls, wsgi) du projet de démo.                          |
| `home/`      | App Wagtail minimale : `HomePage`, et `CustomContentPage` qui remplace `ContentPage`.   |
| `search/`    | Vue de recherche Wagtail standard.                                                      |
| `annuaire/`  | App d’exemple : annuaire de psychologues affiché sur une carte Carte Facile + API REST. |

L’app `annuaire/` est l’implémentation runnable du guide
[**Cas pratique — annuaire de psychologues**](../docs/guide/cas-pratique-annuaire.md)
de la documentation.

## Démarrage

```sh
just setup            # uv sync + migrate + seed (6 psychologues + page publiée)
just createsuperuser  # crée le compte admin Wagtail (optionnel pour visiter le site)
just runserver        # http://localhost:8000
```

Une base `db.sqlite3` créée avant l’ajout de `CustomContentPage` n’est pas
compatible (le modèle de page de contenu doit être choisi avant la première
migration) : supprimez-la et relancez `just setup`.

La page d’annuaire est publiée à <http://localhost:8000/annuaire/>. Pour
éditer le contenu, créer ou supprimer des psychologues, passez par l’admin
Wagtail à <http://localhost:8000/admin/> (**Snippets → Psychologues** /
**Pages**).

L’API REST est exposée en `/api/v2/psychologues/` :

```sh
curl http://localhost:8000/api/v2/psychologues/
curl "http://localhost:8000/api/v2/psychologues/?ville=Paris"
```
