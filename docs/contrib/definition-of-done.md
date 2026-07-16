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
