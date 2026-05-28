# Changelog

Le journal des changements vit désormais sur GitHub : voir la page [Releases du dépôt numerique-gouv/sites-conformes](https://github.com/numerique-gouv/sites-conformes/releases) pour la liste complète des versions.

Les notes de mise à jour qui requièrent une action de l'opérateur (migration de
schéma, gel des contributions, etc.) sont reprises ci-dessous.

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
ne peut pas tolérer d'écritures concurrentes - prévenez les contributeurs,
fermez temporairement l'admin Wagtail, et planifiez la migration en dehors
des heures de pointe.
:::

### Pendant la mise à jour

La commande `python manage.py migrate_from_sites_faciles` doit s'exécuter
**avant** `python manage.py migrate`. Cet ordre garantit que les tables sont
renommées avec leur nouveau préfixe avant que Django n'essaie d'appliquer ses
migrations sur le nouveau schéma.

**Déploiement Scalingo :** le `Procfile` de cette version appelle déjà
`just scalingo-postdeploy`, et cette recette enchaîne automatiquement
`migrate_from_sites_faciles` puis `migrate`. Rien à faire.

**Autres environnements :** si vous déployez avec un autre outil (Docker,
Heroku, Clever Cloud, déploiement manuel), assurez-vous d'exécuter avant la
commande `migrate` existante :

```bash
python manage.py migrate_from_sites_faciles
python manage.py migrate
```

Si votre pipeline appelle `just scalingo-postdeploy` (par exemple via une
recette `deploy` qui l'inclut), aucune action supplémentaire n'est requise -
l'ordre est déjà correct.

### Après la mise à jour

Vérifiez que l'admin Wagtail répond normalement et que les pages publiques se
chargent. Rouvrez la contribution.

En cas de problème, restaurez la sauvegarde prise à l'étape 1 et ouvrez une
[issue sur le dépôt](https://github.com/numerique-gouv/sites-conformes/issues).

### Pour les développeurs

Après un `git pull` sur un clone existant, certains anciens dossiers peuvent
rester à la racine du dépôt à cause des `__pycache__/` qu'ils contiennent
(git ne supprime pas un dossier qui contient des fichiers non suivis).
Purgez-les à la main :

```bash
rm -rf blog/ config/ content_manager/ core/ dashboard/ db_storage/ docs/ \
       events/ forms/ locale/ menus/ proconnect/ static/ templates/ utils/
```
