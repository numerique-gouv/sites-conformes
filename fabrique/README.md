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

**Types de page**
- **Catalogue des produits** (`ProduitsIndexPage`, `/produits/`) : une carte par fiche, avec capture d'écran,
  badge de phase et filtre par phase. Le corps de la page sert d'introduction.
- **Fiche produit** (`ProduitPage`) : mise en page inspirée de beta.gouv.fr et du site mode produit. On y trouve
  un en-tête (mission, phase, lien, capture d'écran), la présentation, un encadré « À propos » (porteurs, contact,
  transparence), la frise des phases et l'équipe avec photos.

**Ce qu'elle fait**
- Elle crée si besoin le catalogue.
- Elle crée ou met à jour une fiche par produit actif.
- Elle dépublie la fiche d'un produit arrêté ou qui a quitté l'incubateur. La fiche reste dans Wagtail.
- Elle ajoute ou met à jour la section « Les équipes produits » de la page `/equipe/`, avec les missions en cours
  uniquement.

**Photos et captures d'écran**
- Elles proviennent de la page publique du produit sur beta.gouv.fr. Elles sont copiées dans la médiathèque, dans la
  collection « beta.gouv.fr », et remplacées si elles changent à la source.
- Si la page beta.gouv.fr est inaccessible, les images déjà importées sont conservées.
- Une personne sans photo sur beta.gouv.fr est affichée avec son initiale.

**Ce qui est mis à jour depuis beta.gouv.fr**
- Sur la fiche : titre, mission, phase et historique des phases, liens, porteurs, équipe, capture d'écran et texte
  de présentation beta.gouv.fr. Ces champs sont en lecture seule dans Wagtail.
- Sur la page Équipe : les blocs dont l'identifiant commence par `betagouv-`.

**Ce qu'elle ne touche jamais**
- Le corps de la fiche. S'il est rempli, il remplace la présentation beta.gouv.fr ; s'il est vide, c'est le texte
  beta.gouv.fr qui s'affiche.
- L'image d'en-tête et les réglages des pages.
- Les autres blocs de la page Équipe, ni leur emplacement.

Une page qui a un brouillon non publié est ignorée jusqu'à ce que le brouillon soit publié. Une nuit sans
changement ne crée aucune révision.

**Corriger une information** (rôle, employeur, phase…) : modifier la fiche dans l'espace membre beta.gouv.fr.
Une correction faite dans Wagtail sur un bloc synchronisé serait écrasée la nuit suivante.

**Variables d'environnement facultatives** : `BETAGOUV_INCUBATOR`, `BETAGOUV_API_BASE`, `FABRIQUE_PRODUCTS_SLUG`,
`FABRIQUE_TEAM_SLUG`.
