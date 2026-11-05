# Fonctions et classes utilitaires

Cette page présente les fonctions et classes réutilisables du projet. Le détail
de chaque paramètre est dans les *docstrings* du code (en anglais) : cette page
explique plutôt à quoi sert chaque outil et où il est déjà utilisé.

Les outils sont rangés en deux familles :

- les modules **`utils`** contiennent des fonctions génériques, qui ne dépendent
  pas des modèles du projet ;
- les modules **`services`** contiennent les fonctions qui créent ou manipulent
  des contenus (pages, menus, collections). Ils ont été séparés des `utils` pour
  éviter des imports circulaires : les modèles importent les `utils`, et les
  `services` importent les modèles.

:::{tip}
Avant d’ajouter une fonction utilitaire, choisissez son module selon cette
règle : si elle importe un modèle du projet, elle va dans `services`, sinon
dans `utils`.
:::

## Images et sites : `sites_conformes/core/utils.py`

`import_image(full_file_path, title)`
: Importe un fichier image du disque dans les médias Wagtail et renvoie l’image
  créée. Chaque appel crée une nouvelle image, même si le fichier a déjà été
  importé. Utilisé par les commandes `create_demo_pages`,
  `import_dsfr_pictograms` et `import_illustration_images`.

`overwrite_image(image, full_file_path, title)`
: Remplace le fichier d’une image existante en conservant son enregistrement et
  son identifiant, donc sans casser les pages qui l’utilisent. Utilisé par
  `import_dsfr_pictograms` et `import_illustration_images` quand l’image existe
  déjà.

`get_closest_image_ratio(image)`
: Renvoie la classe de ratio du DSFR (par exemple `fr-ratio-4x3`) la plus
  proche des proportions d’une image, ou de tout objet qui a une largeur et une
  hauteur (un *rendition*, par exemple). Sans ratio, le DSFR affiche les images
  des médias de contenu en 16:9, ce qui les déforme : le ratio le plus proche est
  celui qui les recadre le moins.

`get_default_site()`
: Renvoie le site par défaut, ou le premier site s’il n’y en a aucun par défaut.
  À utiliser dans les commandes et les scripts, où aucune requête ne permet de
  déterminer le site courant.

## Blocs : `sites_conformes/core/blocks/utils.py`

`help_text_with_details(summary, details, details_label=None)`
: Construit un texte d’aide en deux parties pour l’administration : un résumé
  toujours visible, puis une explication complète dans une section repliable
  (`<details>`), précédée de l’icône d’aide de Wagtail (`HELP_ICON`). Le
  libellé par défaut du bouton est « Comment l’image s’affiche-t-elle ? » :
  passez `details_label` pour un autre type de champ. Le texte de `details`
  n’est pas échappé et peut contenir du HTML.

  ```python
  from django.utils.translation import gettext_lazy as _

  from sites_conformes.core.blocks.utils import help_text_with_details

  image = ImageChooserBlock(
      help_text=help_text_with_details(
          _("Recommended size: at least 800 px wide."),
          _("<strong>On desktop</strong>, the image is displayed to the left of the text."),
      ),
  )
  ```

  Utilisé par les blocs d’images de `basics.py`, `cards.py`, `heros.py` et
  `sections.py`.

`block_to_sample_dict(block)`
: Renvoie une valeur minimale valide pour n’importe quel bloc Wagtail. Les
  `StructBlock` sont remplis récursivement, les `StreamBlock` reçoivent une
  seule entrée, et les blocs de sélection (images, pages, documents, *snippets*)
  renvoient `None` pour que l’appelant y mette un vrai objet. Utilisé par les
  tests (`test_create_demo_pages.py`) pour vérifier que chaque bloc accepte une
  valeur.

`stream_entry(block_name, block_instance)`
: Raccourci qui renvoie le tuple `(block_name, valeur d’exemple)`, prêt à être
  ajouté au contenu d’un `StreamField`.

## Création de contenus : `sites_conformes/core/services/accessors.py`

Ces fonctions renvoient un contenu s’il existe déjà, ou le créent sinon. Elles
peuvent donc être appelées plusieurs fois sans créer de doublons. Elles sont
utilisées par les commandes qui créent les contenus de départ et de
démonstration (`create_starter_pages`, `create_demo_pages`), et sont importées
automatiquement dans `python manage.py shell`.

`get_or_create_collection(col_name)`
: Renvoie la collection qui porte ce nom, ou la crée sous la collection racine.

`get_or_create_content_page(slug, title, body, parent_page=None, ...)`
: Renvoie la `ContentPage` qui a ce *slug* dans la langue du site par défaut, ou
  la crée. Une page existante est renvoyée telle quelle, sans être mise à jour.

- `body` : le contenu du `StreamField`, sous forme de liste de tuples
    `(nom_du_bloc, valeur)` ;
- `parent_page` : par défaut, la page racine du site par défaut ;
- `restriction_type` : ajoute une restriction de consultation à la page créée
    (par exemple `"login"`) ;
- `page_fields` : autres champs à renseigner. Seuls les champs d’en-tête
    (`HEADER_FIELDS`) et `source_url` sont pris en compte.

`get_or_create_catalog_index_page(...)`
: Même fonctionnement, pour une `CatalogIndexPage`.

`get_or_create_main_menu()` et `get_or_create_footer_bottom_menu()`
: Renvoient le menu principal ou le menu du bas de pied de page du site par
  défaut, dans sa langue, et le créent au besoin. Un menu principal nouvellement
  créé contient un lien vers la page d’accueil.

## Import et export de pages : `sites_conformes/core/services/import_export.py`

Ce module copie des pages et leurs images d’une instance Wagtail à une autre, en
passant par l’API (`api/v2/`) du site source. Il sert aux commandes :

- `migrate_pages`, qui copie des pages d’un autre site vers le site local ;
- `export_page_templates` et `import_page_templates`, qui gèrent les modèles de
  pages livrés avec le projet, stockés dans `sites_conformes/core/page_templates/`
  (`pages_data.json` pour les pages, `img/` pour les images).

La chaîne de traitement passe par trois classes :

1. **`ExportPage(source_page_id, source_site)`** récupère une page sur le site
   source et la nettoie : identifiants de blocs, tags, images d’en-tête
   calculées et certaines métadonnées sont retirés. La page nettoyée est dans
   `json_export`, et les identifiants des images qu’elle utilise sont dans
   `image_ids`.
2. **`ImportExportImages(image_ids, source_site=None, image_folder=IMAGES_FOLDER)`**
   télécharge ces images dans `image_folder` avec `download_images()`, avec un
   fichier `image_data.json` qui décrit chacune d’elles. Les pictogrammes du DSFR
   ne sont pas téléchargés, car ils sont déjà présents sur le site cible. La
   méthode `import_images()` importe ensuite les images en local ; une image
   dont le fichier existe déjà (même empreinte) est réutilisée.
3. **`ImportPages(pages_data=None, parent_page_slug=None, image_folder=IMAGES_FOLDER)`**
   importe les images, remplace dans les pages les identifiants des images
   source par ceux des images locales, puis crée les pages avec
   `import_pages()`. Une page déjà importée sous la même page parente (même
   `source_url`) est mise à jour au lieu d’être dupliquée.

:::{note}
`ImportExportImages` crée le dossier `image_folder` et la collection « Images
des modèles de page » dès son instanciation, y compris dans `ImportPages`.
:::

Le module contient aussi deux fonctions qui parcourent la représentation JSON
d’un `StreamField` :

- `remove_block_ids(json_object)` renvoie une copie sans les clés `id` ;
- `update_streamfield_image_ids(json_object, image_ids)` remplace les
  identifiants des clés `image` et `bg_image` par ceux des images locales. Les
  dictionnaires sont modifiés en place.

## ProConnect : `sites_conformes/proconnect/utils.py`

`get_user_by_sub_or_email(sub, email, siret)`
: Cherche l’utilisateur par son identifiant ProConnect (`sub`), puis par son
  adresse e-mail. Dans ce second cas, le lien `UserOIDC` est créé ou mis à jour.
  Renvoie `None` si aucun utilisateur ne correspond : le *backend*
  d’authentification décide alors de créer le compte ou non.

`email_domain_basic_whitelist(user_info)` et `email_domain_db_whitelist(user_info)`
: Exemples de filtres de création de compte. Le premier accepte les adresses en
  `.gouv.fr`. Le second accepte les domaines enregistrés dans la table des
  domaines autorisés (`WhitelistedEmailDomain`), sans inclure leurs
  sous-domaines. Ils renvoient `{"status": "success"}`, ou
  `{"status": "error", "message": …}` avec le message affiché à la personne
  refusée.

Pour activer un filtre, indiquez le chemin complet de la fonction dans la
variable d’environnement `PROCONNECT_USER_CREATION_FILTER` (voir
{doc}`../deploiement/variables-environnement`) :

```bash
PROCONNECT_USER_CREATION_FILTER=sites_conformes.proconnect.utils.email_domain_db_whitelist
```

Pour écrire votre propre filtre, créez une fonction qui reçoit les
informations de l’utilisateur (`user_info`) et renvoie un dictionnaire de la
même forme.

## Mixins

Le projet ne définit pas de *mixin* propre. Les modèles s’appuient sur ceux de
Wagtail et de ses extensions : `RoutablePageMixin` (pages de blog,
d’événements et de catalogue), `TranslatableMixin` (modèles traduisibles) et
`HoneypotFormMixin` et `HoneypotFormSubmissionMixin` (formulaires, fournis par
`wagtail_honeypot`). Leur fonctionnement est décrit dans la
[documentation de Wagtail](https://docs.wagtail.org/en/stable/) et dans celle de
ces extensions.
