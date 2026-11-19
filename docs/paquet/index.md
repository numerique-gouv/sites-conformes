# Sites Conformes Augmenté

Cette section s’adresse aux équipes de développement qui ont besoin de **plus
qu’un site éditorial** : un annuaire, un simulateur, une API, des données
métier… à côté des pages publiées dans le back-office.

« Augmenté », ici, veut dire : Sites Conformes **plus votre code**.

## Instance ou paquet ?

Deux façons d’utiliser Sites Conformes :

| | Déployer une instance | Installer le paquet |
| --- | --- | --- |
| **Ce que vous déployez** | Le dépôt Sites Conformes, tel quel | **Votre** projet Django, qui dépend de Sites Conformes |
| **Pour qui ?** | Toute personne qui veut mettre un site en ligne | Une équipe qui développe en Python et Django |
| **Ajouter votre propre code** | Impossible sans créer un *fork* | Prévu pour : vous écrivez vos applications à côté |
| **Recevoir les nouvelles versions** | Redéployer le dépôt | Mettre à jour une dépendance |

Le paquet est publié sur PyPI sous le nom
[`sites-conformes`](https://pypi.org/project/sites-conformes/). C’est le même
logiciel que le dépôt : modèles de pages, blocs DSFR, menus, back-office. La
différence : **vous** écrivez le projet qui l’entoure. Vous gardez la main sur
les réglages, les URL et les modèles, sans modifier le code de Sites Conformes.

:::{tip}
**C’est quoi un fork ?** Une copie du dépôt que vous modifiez de votre côté.
C’est rapide à mettre en place, mais coûteux ensuite : à chaque nouvelle
version, vos modifications doivent être refusionnées à la main. Le paquet
existe pour éviter ça.
:::

## Quel est votre cas ?

Vous voulez un site, sans rien développer
: Cette section ne vous concerne pas : pour mettre un site en ligne sans
  développer, suivez {doc}`../deploiement/index`.

Vous créez un nouveau projet, avec de la donnée métier à côté du site
: [`bouture`](#deux-outils) vous génère un projet prêt à lancer, auquel vous
  ajoutez votre code. Voir {doc}`nouveau-projet`.

Vous avez déjà un site Django
: Ajoutez-y Sites Conformes sans repartir de zéro ; vous compléterez
  vous-même les réglages et les URL. Voir {doc}`installation`.

Vous maintenez un fork de Sites Conformes
: Revenez au paquet publié en gardant votre base de données et vos contenus.
  C’est le parcours le plus long : testez-le d’abord sur une copie de votre
  site. Voir {doc}`depuis-un-fork`.

## Deux outils

Deux outils en ligne de commande, développés à côté de Sites Conformes, que
vous croiserez dans les pages suivantes :

- [`bouture`](https://github.com/treto-dev/bouture) **crée un projet neuf**,
  déjà configuré — comme `wagtail start` pour Wagtail. Il ne sert qu’au
  démarrage d’un projet.
- [`bern`](https://github.com/treto-dev/bernard) **déplace les pages d’un site
  existant** vers votre propre modèle de page, sans perdre leur contenu ni
  leur historique : voir {ref}`changer-de-modele-site-existant`.

```{toctree}
---
maxdepth: 1
caption: Parcours
---
nouveau-projet
installation
depuis-un-fork
```

```{toctree}
---
maxdepth: 1
caption: Référence
---
configuration
modele-de-page-personnalise
recherche
exemple-annuaire
```
