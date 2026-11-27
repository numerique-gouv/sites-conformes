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
- Les étiquettes : type, équipes et séries de l'événement (elles servent au filtre de l'agenda). Le type et les
  équipes sont aussi affichés sur la carte de l'événement dans la liste de l'agenda et des archives (le type en
  couleur, les équipes avec une icône) ; ils sont gardés à part dans `EtiquettesEvenement`, hors révisions de la page.
- L'image d'en-tête, à partir de la colonne Image (pièce jointe JPG, PNG, WebP ou GIF, 10 Mo au plus ; format
  paysage conseillé). Elle sert de vignette dans la liste de l'agenda et dans la fiche de l'événement, et de bandeau
  en haut de la page. Les images importées sont rangées dans la collection « Agenda » de Wagtail ; chaque fichier
  n'est téléchargé qu'une fois. Une image retirée dans Grist est retirée de la page. Dans la liste, toutes les
  vignettes sont affichées avec à peu près la même surface (filtre `largeur_vignette`) : un logo carré ou une petite
  image ne paraît pas plus petit qu'un logo en longueur. Même chose pour les vignettes de la liste des actualités
  (gabarit `templates/blog/blocks/blog_index_posts_list.html`) ; une actualité sans image y prend le logo du site
  (Configuration du site > Logo). Mieux vaut un logo sans marge blanche autour.
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

### Import de calendriers iCal (Framagenda…)

Avant de lire le Grist, `sync_agenda_grist` importe dans la table `Evenements` les calendriers iCal publics des
équipes qui tiennent déjà leur propre agenda. Par défaut : le Framagenda de Panoramax, l'agenda du site
Voies locales en commun et l'API des événements de la BAN (`https://bal-admin.adresse.data.gouv.fr/api/events`, tout
l'historique depuis 2021 ; public visé suivi dans la colonne Public, type donné à la création) et le Grist de la BAN
(`https://grist.numerique.gouv.fr/o/ban/cS36SuWF2W2z`, table `Evenements` : Adresse-Lab, rencontres régionales ;
seulement les événements validés pour publication ; lu avec `GRIST_API_KEY`, qui doit avoir accès au document ;
les Adresse-Lab reçoivent la série « Adresse-Lab » à la création) (flux iCal de Sites Faciles, `/actualités/ical/`, qui ne contient que les événements à venir). Les équipes continuent
d'utiliser leur calendrier ; les événements arrivent dans le Grist, puis sur le site dans le même passage.

- **Nouvel événement** : ajouté au Grist, **publié**, avec l'équipe du calendrier et la colonne *Source*
  (ex. « Framagenda Panoramax »).
- **Événement déjà importé** : le titre, le début, la fin, le lieu, le lien visio, la page de l'événement, la
  description et l'annulation suivent le calendrier (une modification faite dans Grist sur ces champs est écrasée).
  Le type, l'image, la série, les inscriptions et la case *Publié* restent aux éditeurs du Grist.
- **Lieu** : un lien devient le lien visio ; un lieu comme « Jitsi », « Visio » ou « Webinaire » prend le premier lien
  de la description comme lien visio.
- **Événement à venir retiré du calendrier** : décoché *Publié* dans le Grist, donc dépublié du site. Un événement
  passé n'est jamais dépublié par l'import : il reste dans les archives de l'agenda.
- **Calendrier injoignable ou vide** : rien n'est modifié pour cette source ; les autres continuent.
- `--dry-run` affiche ce qui serait importé sans écrire dans le Grist ; `--sans-calendriers` saute l'import.

La clé `GRIST_API_KEY` doit avoir le droit de modifier le document.

**Liste des calendriers** : variable `AGENDA_CALENDRIERS`, une ligne (ou un `;`) par calendrier, de la forme
`Source | Équipe | URL iCal` (ou `Source | Équipe | URL | ban` pour une API au format de la BAN, `Source | Équipe | URL de l'API du
document | grist-ban` pour un Grist au format de celui de la BAN). Absente : les calendriers par défaut ci-dessus. Vide : aucun import. Pour un Framagenda,
l'URL iCal d'un calendrier public est `https://framagenda.org/remote.php/dav/public-calendars/<jeton>/?export`, où
`<jeton>` est l'identifiant de son lien de partage public. Pensez à ajouter la nouvelle source aux choix de la
colonne *Source* dans le Grist.

## Synchronisation des actualités (Grist + infolettres Brevo)

```sh
python manage.py sync_actualites_grist            # importe les infolettres, puis synchronise
python manage.py sync_actualites_grist --dry-run  # affiche ce qui changerait, sans rien enregistrer
python manage.py sync_actualites_grist --lister   # affiche les campagnes Brevo gardées ou écartées, sans rien écrire
```

Les actualités du site se gèrent dans la table `Actus` du document Grist
[« Actus et Agenda »](https://grist.numerique.gouv.fr/o/fab-donnee-territoriale/habcH4ftoLRf/Actus-et-Agenda/p/4),
plutôt que dans l'administration Wagtail. La commande tourne toutes les 15 minutes sur Scalingo (`cron.json`). Elle
utilise la même clé `GRIST_API_KEY` que l'agenda, qui doit pouvoir modifier le document.

**Colonnes de la table `Actus`** : Titre, Date, Équipe, Source (« Communiqué » ou « Newsletter Brevo »), Publié,
Chapô, Corps (markdown), Lien (version web), Image, Identifiant source, Modifié le.

**Types de page** : ceux de l'app `blog` de Sites Faciles.
- **Actualités** (`BlogIndexPage`) : la page à l'adresse `FABRIQUE_ACTUS_SLUG` (`actualites` par défaut). Si elle
  n'existe pas mais que le site a une seule page d'actualités, c'est celle-là qui est utilisée ; s'il n'en a aucune,
  elle est créée.
- **Article** (`BlogEntryPage`) : un par actu publiée dans Grist.

**Ce qui est mis à jour depuis Grist**
- Le titre, la date et la description (chapô, ou début du texte).
- Les catégories : une par équipe (RNB → « Référentiel National des Bâtiments », BAN → « Base Adresse Nationale »,
  Panoramax ; les autres sont créées si besoin). L'actu remonte ainsi sur la fiche du produit.
- L'étiquette « Newsletter » pour les infolettres, qui permet de les filtrer dans la liste des actualités.
- L'image d'en-tête, à partir de la colonne Image (mêmes règles que pour l'agenda), rangée dans la collection
  « Actualités ».
- Dans le corps, les blocs dont l'identifiant commence par `grist-` : chapô, texte (markdown) et bouton vers le lien
  (« Voir la version e-mail » en haut de l'article pour une infolettre affichée en entier ; en bas, « Lire la
  newsletter » si elle n'a pas de texte, « En savoir plus » pour un communiqué).

**Ce qu'elle ne touche jamais** : les autres blocs du corps, les réglages des pages, les articles écrits à la main
dans Wagtail, sauf les doublons d'infolettres ci-dessous.

**Doublons d'infolettres saisies à la main** : un article écrit dans Wagtail qui reprend une infolettre importée (même
catégorie d'équipe, publié le même jour à un jour près, et qui contient les mêmes images, ou à défaut un mot du titre
en commun) est **dépublié**, pas supprimé. Son ancienne adresse redirige vers la page de l'infolettre (redirection
permanente, visible dans *Paramètres → Redirections*). Les communiqués ne sont jamais concernés.

**Publication** : mêmes règles que l'agenda. Seules les actus dont la case « Publié » est cochée arrivent sur le
site ; une actu décochée ou supprimée dans Grist est dépubliée ; une page avec un brouillon en cours est ignorée ;
une table entièrement vide n'efface rien.

### Import des infolettres Brevo

Avant de lire le Grist, `sync_actualites_grist` importe dans la table `Actus` les infolettres que les équipes
envoient depuis leur propre compte Brevo. Les équipes ne changent rien à leurs habitudes.

- **Seulement les infolettres** : pour chaque compte, on garde les campagnes envoyées dont l'objet commence par un
  texte donné (« Info Panoramax »), ou dont le nom contient un texte donné. Les invitations, alertes aux utilisateurs,
  messages d'accueil ou annonces d'événement sont écartés. `--lister` montre le tri campagne par campagne.
- **Nouvelle infolettre** : ajoutée au Grist, **publiée**, avec l'équipe du compte, la source « Newsletter Brevo »,
  le lien vers la version web et l'aperçu Brevo comme chapô. Le titre est l'objet, complété du mois d'envoi s'il ne
  le contient pas (« Info Voies locales en commun — novembre 2026 »).
- **Contenu** : le HTML de l'e-mail est converti en markdown dans la colonne *Corps* (`fabrique/infolettre_html.py`),
  pour s'afficher sur le site avec les styles DSFR : intertitres, paragraphes, gras, listes, liens et images. L'en-tête
  de l'e-mail (logo, titre, date), son pied (réseaux sociaux, adresse, désinscription), les pixels de suivi et les
  balises Brevo (`{{ contact.PRENOM }}`…) sont retirés. Le résultat se relit et se corrige dans Grist, avec l'aperçu.
- **Images** : sur le site, chaque image seule dans son paragraphe devient un bloc « Image » (largeur « petite »,
  avec son lien), et le fichier est rapatrié dans la médiathèque, collection « Actualités ». Le site ne charge ainsi
  aucune image hébergée chez Brevo (règle « pas de requête vers un autre domaine » de `DOD.md`). Une image déjà
  importée n'est pas retéléchargée ; une image en échec est omise et retentée au passage suivant ; une image au milieu
  d'un paragraphe est retirée (son texte alternatif reste). Dans Grist, le *Corps* garde les adresses Brevo.
- **Infolettre déjà importée** : plus modifiée. Titre, chapô, texte, image, équipe et case *Publié* sont aux éditeurs
  du Grist. Seule exception : un *Corps* vide est rempli avec le contenu converti (pour les infolettres importées avant
  la conversion). Pour retirer une infolettre du site, décochez *Publié* : une ligne supprimée serait recréée.
- **Renvoi correctif** (même objet, même jour) : seule la dernière campagne est gardée ; la première est dépubliée si
  elle avait déjà été importée.
- **Compte illisible** (clé absente ou refusée) : rien n'est modifié pour ce compte ; les autres continuent. Le
  message de Brevo est affiché (« Key not found » : clé SMTP au lieu d'une clé API ; « unrecognised IP address » :
  adresse de Scalingo à autoriser dans le compte Brevo).
- Campagnes lues : celles des 365 derniers jours (`--jours` pour changer). `--sans-newsletters` saute l'import.

**Comptes** : par défaut Panoramax (objet « Info Panoramax », clé dans `BREVO_CLE_PANORAMAX`) et Voies locales
(objet « Info Voies locales », clé dans `BREVO_CLE_VOIES_LOCALES`). Pour en changer, variable `NEWSLETTERS_BREVO`,
une ligne (ou un `;`) par compte, de la forme `Équipe | VARIABLE_DE_LA_CLE | objet: texte` ou
`… | nom: texte`. Exemple pour la BAN, dont le site filtre déjà sur le nom :
`BAN | BREVO_CLE_BAN | nom: adresse.data.gouv.fr`. L'équipe doit figurer dans les choix de la colonne *Équipe* du
Grist.

**Clé API Brevo** : dans Brevo, menu du compte → *SMTP et API* → *Clés API* → *Générer une nouvelle clé*. Une clé
Brevo donne accès à tout le compte : créez-en une dédiée au site, et mettez-la seulement dans les variables
d'environnement Scalingo.

**Variables d'environnement facultatives** : `FABRIQUE_ACTUS_SLUG`, `NEWSLETTERS_BREVO`, et celles de l'agenda pour
le document Grist (`GRIST_BASE_URL`, `GRIST_AGENDA_ORG`, `GRIST_AGENDA_DOC_ID`).

### Vue calendrier de la page Agenda

La page `/agenda/` s'ouvre sur un calendrier du mois (`fabrique/calendrier.py`, gabarit
`fabrique/templates/fabrique/agenda/calendrier.html`, styles dans `fabrique/static/fabrique/agenda.css`). La liste de
cartes de Sites Faciles reste disponible avec le bouton « Liste » (`?vue=liste`) ; les archives restent en liste.

- `?mois=AAAA-MM` choisit le mois ; les filtres par étiquette et par catégorie s'appliquent aussi au calendrier.
- Couleur de chaque événement d'après son équipe dans Grist (Panoramax, RNB, BAN, Voies locales, Fabrique, dans cet
  ordre de priorité) ; gris sinon. Événements annulés barrés ; événements sur plusieurs jours répétés chaque jour.
- Au-delà de 3 événements dans une journée : « + N autres », vers la liste de ce jour.
- Petit écran : la grille est remplacée par la liste des jours qui ont des événements.
- Point d'entrée : `templates/events/blocks/events_index_posts_list.html` (copie du gabarit de Sites Faciles), qui
  affiche le calendrier ou les cartes selon la vue.

### Abonnement à l'agenda (flux iCal)

Deux flux iCal (`fabrique/flux.py`, URL `/flux/<nom>.ics`), proposés sur `/agenda/` par des liens `webcal://`
(abonnement direct dans Outlook et Apple Calendrier) et une adresse `https://` à coller dans Google Agenda :

- `agenda-fabrique` : l'essentiel — tous les événements de la Fabrique (équipe « Fabrique de la donnée territoriale »
  dans Grist, ou événement saisi à la main dans Wagtail) et seulement les comités des équipes (type ou étiquette
  commençant par « Comité ») ;
- `agenda-complet` : tous les événements.

Les flux gardent les événements terminés depuis moins de 3 mois, marquent `STATUS:CANCELLED` les événements
« Annulé : … », et indiquent un rafraîchissement toutes les 4 heures. Ils remplacent, sur la page, le bouton de
téléchargement iCal de Sites Faciles (`/agenda/ical/`, toujours en ligne).

## Mise à jour de la page d'accueil

```sh
python manage.py maj_accueil --dry-run   # affiche ce qui changerait, sans rien enregistrer
python manage.py maj_accueil             # enregistre un brouillon de l'accueil, à prévisualiser puis publier dans Wagtail
python manage.py maj_accueil --publier   # publie directement
python manage.py maj_accueil --menu      # réordonne aussi le menu principal (effet immédiat, pas de brouillon)
```

Commande ponctuelle, pas lancée par le cron. La migration `fabrique/0003_maj_accueil` l'a lancée une fois au
déploiement, en brouillon (sans `--menu`), à la place d'un `scalingo run` ; elle ne bloque jamais le déploiement et
écrit son rapport dans le journal (lignes `maj_accueil`). Elle complète l'accueil saisi dans Wagtail pour y faire apparaître les
pages Produits, Agenda et Actualités. Elle ne retire ni ne réécrit rien : elle repère les sections par leur texte et
y ajoute des éléments. On peut la relancer sans créer de doublons.

**Ce qu'elle ajoute**
- **Bandeau** : boutons « Découvrir nos produits » et « Voir l'agenda ». Dans les boutons de l'en-tête si la page
  en affiche un, sinon dans un bloc « Liste de boutons » juste après le bloc d'introduction.
- **Avant « Comment ça marche ? »** : un bloc « Prochains rendez-vous » (4 événements à venir) et un bloc
  « Dernières actualités » (4 actualités). Leurs gabarits (`templates/content_manager/blocks/`) reprennent les
  cartes de l'agenda et des actualités : dates de l'événement, type et équipes, vignette entière, abonnement iCal.
- **Encart « Projets sélectionnés par le comité des partenaires »** : lien vers le dernier compte rendu du comité
  (l'actualité la plus récente dont le titre contient « comité des partenaires »).
- **Gouvernance** : sous chaque description (Collectif vigie, Comité des partenaires, Comités d'investissement), un
  lien vers l'agenda filtré sur l'étiquette du type d'événement, ou vers le compte rendu du comité.
- **Menu**, avec `--menu` seulement : Accueil, Produits, Agenda, Actualités, puis Partenaires et Équipe.

Les blocs ajoutés ont un identifiant qui commence par `accueil-`. On peut ensuite les déplacer ou les régler dans
Wagtail (nombre de cartes, filtre par étiquette…). Un réglage modifié sur un bloc `accueil-` est remis à sa valeur
par défaut si on relance la commande. Une section introuvable est signalée et laissée telle quelle. Si l'accueil a un
brouillon non publié, la commande s'arrête sans rien faire.
