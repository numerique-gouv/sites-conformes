## Format du fichier notifications.json

Ce fichier est consommé par le panneau d'information de l'admin Sites Conformes.
Il permet d'envoyer des notifications sur les différents back-office.   

Les champs disponibles :
- `type` : `info`, `warning` ou `alert` (changer les couleurs de la notification)
- `title` : titre du message (optionnel)
- `description` : description courte (optionnel)
- `url` : lien "En savoir plus" (optionnel)
- `date` : date de publication (YYYY-MM-DD, optionnel)
- `end_date` : date d'expiration, ne s'affiche pas mais permet de faire disparaitre automatiquement la notification sinon celle-ci reste épinglée. (YYYY-MM-DD, optionnel)

Automatiquement, une notification est envoyée si la version installée n'est pas la même que la dernière version sortie. 

Il est nécessaire de conserver le format du fichier. Les trois premiers items sont des templates pour permettre leur réutilisation, veillez à les conserver en l'état.

