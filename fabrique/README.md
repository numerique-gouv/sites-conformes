# Application `fabrique`

Personnalisations du site de la Fabrique de la donnée territoriale, à part du code de Sites Faciles.

## Synchronisation beta.gouv.fr

```sh
python manage.py sync_betagouv            # synchronise
python manage.py sync_betagouv --dry-run  # affiche ce qui changerait, sans rien enregistrer
```

La commande lit l'API publique de beta.gouv.fr (`startups.json` et `authors.json`), générée à partir du dépôt
[betagouv/beta.gouv.fr](https://github.com/betagouv/beta.gouv.fr). Elle traite les produits de l'incubateur
`fab-geocommuns`. Elle tourne chaque nuit sur Scalingo (`cron.json`).

**Ce qu'elle fait**
- Elle crée si besoin la page catalogue `/produits/`, avec un filtre par phase.
- Elle crée ou met à jour une page par produit actif.
- Elle dépublie la page d'un produit abandonné ou qui a quitté l'incubateur. La page reste dans Wagtail.
- Elle ajoute ou met à jour la section « Les équipes produits » de la page `/equipe/`, avec les missions en cours
  uniquement.

**Champs mis à jour depuis beta.gouv.fr**
- Titre de la page, description (le « pitch ») et étiquette de phase.
- Blocs dont l'identifiant commence par `betagouv-` : badge de phase, mission, liens et porteurs, équipe.

**Ce qu'elle ne touche jamais**
- Tous les autres blocs de la page, notamment la présentation rédigée à la création, qu'on peut réécrire librement.
- L'image d'en-tête et les réglages de la page.
- L'emplacement des blocs : on peut déplacer les blocs synchronisés dans la page, ils restent à leur place.

Une page qui a un brouillon non publié est ignorée jusqu'à ce que le brouillon soit publié. Une nuit sans
changement ne crée aucune révision.

**Corriger une information** (rôle, employeur, phase…) : modifier la fiche dans l'espace membre beta.gouv.fr.
Une correction faite dans Wagtail sur un bloc synchronisé serait écrasée la nuit suivante.

**Variables d'environnement facultatives** : `BETAGOUV_INCUBATOR`, `BETAGOUV_API_BASE`, `FABRIQUE_PRODUCTS_SLUG`,
`FABRIQUE_TEAM_SLUG`.
