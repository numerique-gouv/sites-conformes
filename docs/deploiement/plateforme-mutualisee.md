# Plateformes mutualisées (grande échelle)

Les autres méthodes de cette section déploient **un** site à la fois. Lorsqu'une administration doit héberger **un grand nombre** d'instances de Sites Conformes (une « usine à sites »), on passe à une plateforme mutualisée qui crée et gère ces instances automatiquement. Deux approches existent : une plateforme Kubernetes auto-hébergée (Ciel7) ou un gestionnaire qui pilote des PaaS externes (`sites-faciles-saas`).

## À grande échelle : plateforme mutualisée (Kubernetes) — 🟣 Expert

Cette section décrit une telle plateforme, **Ciel7**, à titre d'exemple d'architecture (voir avec l'académie de Nancy pour plus d'informations).

> ℹ️ **Architecture, pas procédure.** Contrairement aux autres pages de cette section, il ne s'agit pas d'un pas-à-pas d'installation : monter une telle plateforme relève d'une équipe d'infrastructure. Le but ici est de **comprendre comment elle fonctionne** et où se situe l'application Sites Conformes dans l'ensemble.

### L'idée générale

Ciel7 est l'équivalent « maison » d'un PaaS comme Scalingo, mais hébergé par l'administration elle-même. C'est une plateforme qui sait, à la demande, **fabriquer un nouveau site Sites Conformes** complet (avec sa base de données et son stockage), le mettre en ligne, le modifier ou le supprimer — le tout depuis une interface d'administration, sans réinstaller quoi que ce soit à la main.

Pour tenir la charge de nombreux sites et rester disponible même en cas de panne d'une machine, elle s'appuie sur **Kubernetes**.

> 💡 **C'est quoi Kubernetes (K8s) ?** Là où Docker fait tourner des conteneurs sur **une** machine, Kubernetes orchestre des conteneurs sur **une flotte** de machines. Il répartit les applications sur les serveurs disponibles, relance automatiquement ce qui tombe en panne, et équilibre le trafic. C'est l'outil de référence pour faire tourner beaucoup d'applications de façon fiable.

> 💡 **C'est quoi un « pod » ?** Dans le vocabulaire Kubernetes, un *pod* est la plus petite unité déployable : en pratique, un conteneur (ou un petit groupe de conteneurs) qui exécute un bout de l'application. Un site Sites Conformes est composé de plusieurs pods (voir plus bas).

### Comment le trafic arrive jusqu'à un site

Quand un visiteur ouvre un site hébergé sur la plateforme, sa requête traverse plusieurs couches, de l'extérieur vers l'intérieur :

1. **Les frontaux web** (deux serveurs, *Web Frontend 1 & 2*) : ce sont les portes d'entrée. Ils reçoivent tout le trafic externe et le répartissent (*load balancing*). En avoir deux garantit que si l'un tombe, l'autre prend le relais.
2. **Le plan de contrôle Kubernetes** (trois *Masters*) : c'est le cerveau du cluster, en triple exemplaire pour la fiabilité. Il aiguille chaque requête HTTP/HTTPS vers le bon site, et décide où placer les applications sur les machines.
3. **Les nœuds workers** (quatre machines, *worker-01* à *worker-04*) : ce sont elles qui font tourner concrètement les sites (les pods). C'est la « puissance de calcul » de la plateforme.

> 💡 **Pourquoi tout est en plusieurs exemplaires ?** C'est le principe de la **haute disponibilité** : en doublant ou triplant chaque élément critique (frontaux, cerveau du cluster, machines), la plateforme continue de fonctionner même si un composant tombe en panne.

### L'écosystème Ciel7 : ce qui automatise la création des sites

C'est la partie spécifique à la plateforme (par-dessus Kubernetes). Elle se compose de :

- **L'interface Ciel7** (*Pod Interface*) : l'écran d'administration où une personne autorisée crée, modifie ou supprime un site, en quelques clics.
- **L'orchestrateur Ciel7** (*Pod Orchestrator*) : le moteur en arrière-plan. **Toutes les minutes**, il consulte une liste de tâches (la table `tache` de la base Ciel7) ; dès qu'une demande y apparaît (« créer tel site », « modifier tel autre »), il l'exécute en commandant Kubernetes.
- **La base MariaDB de Ciel7** (sur une machine séparée, hors du cluster) : elle stocke l'état de la plateforme — la configuration des sites, l'historique des créations, les journaux. C'est la mémoire de Ciel7.

> ⚠️ **À ne pas confondre :** la base **MariaDB** est celle de la *plateforme* Ciel7, pas celle des sites. Chaque site Sites Conformes garde sa **propre base PostgreSQL** (voir ci-dessous). Les deux ne se mélangent pas.

### Un site Sites Conformes dans ce décor

C'est le point rassurant : au niveau d'un site individuel, **on retrouve exactement l'application décrite dans le reste de cette documentation**. Chaque instance est composée de trois pods :

1. **Pod Site-Conforme** : l'application Django/Wagtail elle-même (le serveur web du site).
2. **Pod Python Médias** : le service qui gère les images et documents du site.
3. **Pod PostgreSQL** : la base de données propre à ce site.

Autrement dit, Ciel7 ne change rien à *ce qu'est* Sites Conformes : la plateforme se contente de **fabriquer et piloter en masse** ces trios de pods. Les variables d'environnement, les migrations, les commandes Django décrites ailleurs dans cette section restent les mêmes — elles sont simplement appliquées automatiquement par l'orchestrateur au lieu d'être tapées à la main.

> 📄 Cette description est une vue d'ensemble vulgarisée. Pour déployer ou opérer une telle plateforme, reportez-vous à la documentation technique détaillée de Ciel7 (configuration Kubernetes, images des conteneurs, mise en place de l'orchestrateur), qui dépasse le cadre de ce guide.

## Gestionnaire de déploiement — 🔵 Confirmé

Dans la même logique que Ciel7 (gérer plusieurs instances plutôt qu'un site isolé), l'équipe Sites Faciles maintient un **gestionnaire de déploiements** officiel : `sites-faciles-saas`. C'est une application Django qui automatise la création d'instances de Sites Conformes **sur des plateformes PaaS** (Scalingo et Alwaysdata), via leurs API.

Concrètement, plutôt que de réaliser à la main les étapes de la page {doc}`scalingo` pour chaque nouveau site, on passe par une interface qui enchaîne automatiquement les étapes du déploiement (création de l'app, base de données, configuration, mise en ligne) pour le compte du demandeur. C'est l'outil qui fait tourner l'offre mutualisée officielle.

> 💡 **Ciel7 ou sites-faciles-saas ?** Les deux jouent le même rôle (fabriquer des instances à la demande), mais sur des socles différents : Ciel7 s'appuie sur un cluster **Kubernetes** auto-hébergé, tandis que `sites-faciles-saas` pilote des **PaaS** externes (Scalingo, Alwaysdata). Le second est plus simple à opérer si vous utilisez déjà ces plateformes ; le premier offre davantage de contrôle sur l'infrastructure.

Pour aller plus loin :

- Installation en local : voir {doc}`../contrib/installation-locale`.
- Guide d'utilisation : la [documentation officielle de Sites Faciles](https://sites.beta.gouv.fr/documentation/gestionnaire-de-sites/).

> 💡 Pour information : Sites Conformes offre également un mode multisite permettant de gérer plusieurs sites au sein d'une même instance.
