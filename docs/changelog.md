# Changelog

Le journal des changements vit désormais sur GitHub : voir la page
[Releases du dépôt numerique-gouv/sites-conformes](https://github.com/numerique-gouv/sites-conformes/releases)
pour la liste complète des versions.

Les notes de mise à jour qui requièrent une action de l’opérateur (migration de
schéma, gel des contributions, etc.) sont reprises ci-dessous.

## Prochaine version - Suppression des données de l’ancien système de menus

Les menus ont été convertis vers l’application `sites_conformes.menus` lors
du passage à la v4. Cette version supprime ce qui restait de l’ancien
système :

- les entrées de l’application obsolète `wagtailmenus` (menus principaux,
  menus « plats » et leurs éléments) sont effacées par la migration
  `sites_conformes_menus.0004_delete_legacy_menu_entries` ;
- les modèles `MegaMenu` et `MegaMenuCategory` de `sites_conformes_core`
  et leurs tables sont supprimés ;
- le processeur de contexte `sites_conformes.core.context_processors.mega_menus`
  est déprécié : il ne fait plus rien et peut être retiré de vos réglages
  `TEMPLATES`.

:::{important}
`wagtailmenus` reste installé dans cette version, car la conversion des
anciens menus en a besoin. Il sera retiré dans une version ultérieure :
**passez par cette version avant de monter vers celle-là**, sans quoi vos
anciens menus ne seraient pas convertis.
:::

## Prochaine version - Fichiers statiques servis par WhiteNoise

Quand `SF_USE_WHITENOISE=1`, les fichiers statiques étaient en réalité servis
par `dj-static`, qui enveloppait l’application dans `config/wsgi.py` et
interceptait les requêtes avant WhiteNoise. C’est désormais WhiteNoise qui les
sert, compressés en gzip et brotli, avec un cache navigateur illimité pour les
fichiers hashés par `collectstatic`.

- La variable `SF_PROD_SERVE_STATIC` est supprimée : elle n’avait pas d’utilité
  avec WhiteNoise et empêchait de servir les statiques depuis un sous-répertoire
  (`FORCE_SCRIPT_NAME`). Vous pouvez la retirer de vos variables
  d’environnement.
- Si votre projet a son propre `settings.py`, placez
  `whitenoise.middleware.WhiteNoiseMiddleware` juste après
  `django.middleware.security.SecurityMiddleware` (voir {doc}`paquet/configuration`).

## v4.0.0 - Packagification

Cette version transforme `sites-conformes` en package Python distribué sur
PyPI, indépendant du projet Django hôte. Les apps internes sont préfixées par
`sites_conformes_*` et les tables de la base de données sont renommées en
conséquence.

### Avant la mise à jour

:::{warning}
**Faites une sauvegarde de la base de données.** La migration renomme les
tables existantes en place. Une sauvegarde permet de revenir en arrière si
quoi que ce soit se passe mal.
:::

:::{warning}
**Gelez les contributions pendant la mise à jour.** Le renommage des tables
ne peut pas tolérer d’écritures concurrentes - prévenez les contributeurs,
fermez temporairement l’admin Wagtail, et planifiez la migration en dehors
des heures de pointe.
:::

### Pendant la mise à jour

La commande `python manage.py migrate_to_packaged_version` doit s’exécuter
**avant** `python manage.py migrate`. Cet ordre garantit que les tables sont
renommées avec leur nouveau préfixe avant que Django n’essaie d’appliquer ses
migrations sur le nouveau schéma.

**Déploiement Scalingo :** le `Procfile` de cette version appelle déjà
`just scalingo-postdeploy`, et cette recette enchaîne automatiquement
`migrate_to_packaged_version` puis `migrate`. Rien à faire.

**Autres environnements :** si vous déployez avec un autre outil (Docker,
Heroku, Clever Cloud, déploiement manuel), assurez-vous d’exécuter avant la
commande `migrate` existante :

```sh
python manage.py migrate_to_packaged_version
python manage.py migrate
```

Si votre pipeline appelle `just scalingo-postdeploy` (par exemple via une
recette `deploy` qui l’inclut), aucune action supplémentaire n’est requise -
l’ordre est déjà correct.

### Après la mise à jour

Vérifiez que l’admin Wagtail répond normalement et que les pages publiques se
chargent. Rouvrez la contribution.

En cas de problème, restaurez la sauvegarde prise à l’étape 1 et ouvrez une
[issue sur le dépôt](https://github.com/numerique-gouv/sites-conformes/issues).

### Pour les développeurs

Après un `git pull` sur un clone existant, certains anciens dossiers peuvent
rester à la racine du dépôt à cause des `__pycache__/` qu’ils contiennent
(git ne supprime pas un dossier qui contient des fichiers non suivis).
Purgez-les à la main :

```sh
rm -rf blog/ config/ content_manager/ core/ dashboard/ db_storage/ docs/ \
       events/ forms/ locale/ menus/ proconnect/ static/ templates/ utils/
```

### ProConnect

La variable `PROCONNECT_USER_CREATION_FILTER` utilise le chemin complet de la fonction
de filtre. Si une fonction commençant par `proconnect.utils` était définie, il faut
ajouter `sites_conformes.` devant. Par exemple

```sh
PROCONNECT_USER_CREATION_FILTER=proconnect.utils.email_domain_db_whitelist
```

devient

```sh
PROCONNECT_USER_CREATION_FILTER=sites_conformes.proconnect.utils.email_domain_db_whitelist
```
