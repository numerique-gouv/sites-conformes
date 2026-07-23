# Migrer un site vers un autre hébergement — 🔵 Confirmé

Cette page décrit comment déplacer un site Sites Conformes **déjà en service** d'un
hébergement vers un autre : de Scalingo vers un serveur Linux, d'un VPS vers
Docker, d'un ministère vers un autre, etc.

Le principe est toujours le même, quel que soit le sens de la migration :
l'application elle-même n'a rien de spécifique à son hébergeur, **seules les
données et la configuration voyagent**.

## Ce qui doit être transféré

| Élément | Où il vit | Comment il voyage |
| --- | --- | --- |
| **La base PostgreSQL** | base de données | export (`pg_dump`) puis import |
| **Les fichiers médias** | disque local ou stockage S3 | copie ou synchronisation |
| **Les variables d'environnement** | `.env` ou tableau de bord du PaaS | à recréer sur la cible |
| **Le domaine** | DNS | bascule au dernier moment |

Le code, lui, n'a pas à être « transféré » : on l'installe sur la cible comme
pour une installation neuve.

> ⚠️ **Gelez les contributions pendant la bascule.** Toute page publiée sur
> l'ancienne instance après l'export sera perdue. Prévenez les personnes qui
> éditent, et gardez la fenêtre de migration courte.

## 1. Faire l'inventaire de la source

Avant toute chose, notez :

- **le backend de stockage des médias** utilisé : disque local ou S3 (variable `S3_HOST` renseignée) — voir {doc}`../donnees/sauvegarde-restauration` ;
- **la liste des variables d'environnement** actuellement définies (voir {doc}`variables-environnement`) ;
- **la version** de Sites Conformes en service, pour installer au moins la même sur la cible.

## 2. Sauvegarder la source

Exportez la base :

```bash
pg_dump -U <utilisateur> <base> > sauvegarde.sql
```

Sur Scalingo, la base est sauvegardée automatiquement : téléchargez la dernière
sauvegarde depuis l'interface de l'addon PostgreSQL.

Récupérez également les fichiers médias, selon le backend utilisé :

- **stockage sur disque** : copiez le dossier des médias ;
- **stockage S3** : synchronisez le bucket, soit en ligne de commande avec `rclone`, soit avec un client graphique compatible S3 comme [Cyberduck](https://cyberduck.io/) — pratique si vous préférez éviter le terminal.

> ℹ️ **Si le S3 est hébergé par l'équipe Sites Conformes**, vous n'avez pas
> forcément la main sur le bucket ni les clés d'accès. Contactez l'équipe à
> [contact@sites.beta.gouv.fr](mailto:contact@sites.beta.gouv.fr) pour récupérer
> les fichiers ou obtenir les accès nécessaires.

Les recettes `just` du projet peuvent aider pour cette étape : voir
{doc}`../donnees/sauvegarde-restauration`.

## 3. Préparer l'instance cible

Installez Sites Conformes sur le nouvel hébergement en suivant la méthode
correspondante — {doc}`scalingo`, {doc}`serveur-linux` ou {doc}`docker` — **en
vous arrêtant avant l'initialisation du contenu** : inutile de créer les pages de
démarrage, elles seront remplacées par vos données.

Recréez les variables d'environnement relevées à l'étape 1. Gardez pour l'instant
l'ancien domaine dans `HOST_URL` et `ALLOWED_HOSTS` : vous les changerez à l'étape 5.

## 4. Restaurer la base et les médias

Importez la base :

```bash
psql -U <utilisateur> -d <base> < sauvegarde.sql
```

Puis appliquez les migrations, au cas où la cible tournerait une version plus
récente :

```bash
python manage.py migrate
```

Remettez ensuite les médias en place : copiez les fichiers vers le disque de la
cible, ou téléversez-les dans le bucket S3 avec `rclone` ou
[Cyberduck](https://cyberduck.io/).

> 💡 **Profitez-en pour passer au S3** si ce n'est pas déjà le cas : le stockage
> objet est la configuration recommandée en production.

## 5. Basculer le domaine

C'est l'étape la plus sensible : le nom de domaine du site est stocké **à la fois**
dans les variables d'environnement et **dans la base de données**.

Mettez à jour les variables sur la cible :

- `HOST_URL` — le nouveau domaine, **nom de domaine seul**, sans `https://` ni port (l'application refuse de démarrer sinon) ;
- `ALLOWED_HOSTS` — doit contenir le nouveau domaine ;
- `CSRF_TRUSTED_ORIGINS` et `WAGTAILADMIN_BASE_URL` si vous les aviez définies explicitement.

Puis **répercutez le domaine en base** :

```bash
python manage.py set_config
```

Cette commande réécrit le nom d'hôte du site Wagtail à partir de `HOST_URL`. Sans
elle, le site continuerait de générer des liens vers l'ancien domaine.

Basculez enfin le DNS vers le nouvel hébergement.

## 6. Finaliser

```bash
python manage.py collectstatic --noinput --ignore="*.sass"
python manage.py update_index
```

`update_index` reconstruit l'index de recherche, qui n'est pas transféré avec la base.

## 7. Vérifier avant de couper l'ancienne instance

- Le site public répond sur le nouveau domaine.
- La connexion au back-office fonctionne (`/cms-admin/` par défaut).
- **Les images et documents s'affichent** — c'est le symptôme le plus fréquent d'un transfert de médias incomplet.
- La recherche renvoie des résultats.
- Un envoi d'e-mail fonctionne (formulaire de contact, réinitialisation de mot de passe).

> 🔙 **Gardez l'ancienne instance en état de marche** quelques jours après la
> bascule, le temps que le DNS se propage partout et que d'éventuels problèmes
> apparaissent. C'est votre seul retour arrière.
