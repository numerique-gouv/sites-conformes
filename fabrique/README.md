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

## Synchronisation de l'agenda Grist

```sh
python manage.py sync_agenda_grist            # synchronise
python manage.py sync_agenda_grist --dry-run  # affiche ce qui changerait, sans rien enregistrer
```

La commande lit la table `Evenements` du document Grist
[« Agenda »](https://grist.numerique.gouv.fr/o/fab-donnee-territoriale/habcH4ftoLRf/Agenda), construit sur le modèle de
l'agenda du site mode produit (mêmes colonnes). Elle tourne toutes les 15 minutes sur Scalingo (`cron.json`).

**Variable d'environnement obligatoire** : `GRIST_API_KEY`, la clé API d'un compte qui a accès au document
(Grist → Paramètres du profil → Clé API). Sur Scalingo, elle se règle dans l'onglet *Environment* de l'application.
Le mieux est d'utiliser un compte qui n'a que l'accès en lecture au document.

**Types de page** : ceux de l'app `events` de Sites Faciles.
- **Agenda** (`EventsIndexPage`, `/agenda/`) : événements à venir, archives, filtre par étiquette, export iCal. Créée
  si elle n'existe pas. Le corps de la page sert d'introduction.
- **Événement** (`EventEntryPage`) : une page par événement publié dans Grist.

**Ce qui est mis à jour depuis Grist**
- Le titre (précédé de « Annulé : » si l'événement est annulé), les dates de début et de fin, le lieu (« En ligne »
  s'il n'y a qu'un lien de visio) et le lien d'inscription.
- Les étiquettes : type, équipes et séries de l'événement.
- L'image d'en-tête, à partir de la colonne Image (pièce jointe JPG, PNG, WebP ou GIF, 10 Mo au plus ; format
  paysage conseillé). Elle sert de vignette dans la liste de l'agenda et dans la fiche de l'événement, et de bandeau
  en haut de la page. Les images importées sont rangées dans la collection « Agenda » de Wagtail ; chaque fichier
  n'est téléchargé qu'une fois. Une image retirée dans Grist est retirée de la page.
- Dans le corps, les blocs dont l'identifiant commence par `grist-` : alerte d'annulation, public et places restantes,
  description (markdown) et boutons (s'inscrire, rejoindre la visio, page de l'événement, ajouter à Outlook).

**Ce qu'elle ne touche jamais**
- Les autres blocs du corps, ni leur emplacement. On peut par exemple ajouter une vidéo ou un programme détaillé
  sous les blocs synchronisés.
- Les réglages des pages et les événements créés à la main dans Wagtail.
- Une image d'en-tête choisie à la main dans Wagtail, tant que l'événement n'a pas d'image dans Grist.

**Publication**
- Seuls les événements dont la case « Publié » est cochée dans Grist arrivent sur le site.
- Un événement décoché ou supprimé dans Grist est dépublié. Sa page reste dans Wagtail et revient en ligne s'il est
  republié.
- Les événements passés restent en ligne : ils passent dans les archives de l'agenda.
- Une page qui a un brouillon non publié est ignorée jusqu'à ce que le brouillon soit publié.
- Garde-fou : si la table Grist est entièrement vide alors que des événements sont en ligne, la synchronisation
  s'arrête sans rien changer. Pour retirer un événement, décochez « Publié ».

**Variables d'environnement facultatives** : `GRIST_BASE_URL`, `GRIST_AGENDA_ORG`, `GRIST_AGENDA_DOC_ID`,
`FABRIQUE_AGENDA_SLUG`.
