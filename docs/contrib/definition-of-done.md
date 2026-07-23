# Définition du fini

Ce document liste les éléments à vérifier afin de déclarer qu’une fonctionnalité est terminée et peut être déployée.

- [ ] La fonctionnalité est couverte par des tests automatisés
  - [ ] L’ensemble des tests passe sans erreurs
- [ ] La documentation technique et utilisateur est mise à jour si nécessaire.
- [ ] Tous les éléments présents dans le code respectent les conventions de nommage du projet
- [ ] Tous les éléments présents dans le code sont en anglais
- [ ] Tous les éléments textuels s’affichent en français
- [ ] Si des modèles ont été modifiés, l’API est-elle toujours fonctionnelle ?
- [ ] L’application est conforme au [RGAA v4.1](https://accessibilite.numerique.gouv.fr/)
  - [ ] Les éléments de contenus non-textuels sont assortis d’équivalents textuels
  - [ ] Les éléments sont visuellement perceptibles, notamment en utilisant des contrastes suffisants et en ne communiquant pas d’information uniquement par la couleur
  - [ ] Le balisage sémantique est correctement utilisé (e.g utiliser `<caption>` pour les tableaux, les bonnes balises pour indiquer les colonnes d’en-tête, etc.)
  - [ ] L’application est utilisable au clavier
  - [ ] L’information est présentée de manière cohérente et structurée, en utilisant un balisage sémantiques (`<hx>`, `<section>`, `<nav>`, etc.)
  - [ ] L’application reste utilisable avec un agrandissement de police de 200%
  - [ ] Les formulaires sont correctement balisés (utilisation de labels, intitulés des boutons explicites)
- [ ] La navigation est facilitée (fil d’Ariane, contenus faciles à trouver, pas d’imbrication trop profondes des pages, etc.)
- [ ] L’application est conforme au RGPD
  - [ ] Les données personnelles collectées sont pertinentes et nécessaires au fonctionnement du service
  - [ ] Les données sont collectées après recueil d’un consentement explicite de l’usager·e
  - [ ] L’usager·e est informé·e de l’utilisation qui sera faite des données collectées
  - [ ] L’usager·e dispose d'un moyen de consulter / rectifier / supprimer ses données
  - [ ] L’application ne génère pas de requête http vers un autre domaine (trackers)
- [ ] L’application est sécurisée
  - [ ] Aucun secret ou mot de passe n’est en dur dans le code
  - [ ] Aucune donnée sensible n’apparaît dans les messages d’erreur. En particulier, la stacktrace ne doit pas appaître en production.
  - [ ] Les formulaires utilisent CSRF
  - [ ] Les droits d’accès à la fonctionnalité et aux pages (public, restreint aux administrateurs et/ou à certains groupes) sont cohérents avec le besoin
  - [ ] Les injections SQL sont impossibles (Utilisation exclusive de l’ORM de Django, pas de requêtes SQL brutes non sécurisées.)
  - [ ] Limiter le nombre de dépendances et, si nécessaire d’en ajouter une, vérifier qu’elle est maintenue

---

> Ce document est vivant et doit évoluer avec le projet. Toute modification doit être validée par l’équipe de développement.
