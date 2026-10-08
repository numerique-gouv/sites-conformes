# Superviser les erreurs avec Sentry — 🔵 Confirmé

[Sentry](https://sentry.io) est un service de **supervision des erreurs** : dès
qu’une page de votre site plante (erreur 500, exception dans le code), Sentry
reçoit automatiquement un rapport détaillé et peut vous prévenir par e-mail.
Vous êtes ainsi informé d’un problème avant même qu’un visiteur le signale, et
vous disposez des informations nécessaires pour le corriger ou le transmettre à
l’équipe de Sites Conformes.

Chaque rapport contient notamment :

- la **trace complète de l’erreur** (fichier, ligne, valeurs des variables) ;
- la **requête** qui l’a provoquée (adresse de la page, méthode, en-têtes) ;
- l’**utilisateur connecté**, le cas échéant, si vous l’autorisez (voir
  [Données personnelles](#donnees-personnelles)) ;
- l’**environnement** (production, recette…) et le nombre d’occurrences.

Sentry est **optionnel** et **désactivé par défaut** : tant que la variable
`SENTRY_DSN` n’est pas renseignée, aucune donnée n’est envoyée.

## Prérequis

- **Un compte Sentry.** Vous pouvez utiliser le service hébergé
  [sentry.io](https://sentry.io), une instance auto-hébergée, ou une instance
  mutualisée proposée par votre administration : renseignez-vous auprès de votre
  équipe informatique avant d’en créer une nouvelle. Pour les start-up d'État,
  une instance est mise à disposition. (cf. [doc de Beta.gouv.fr](https://doc.incubateur.net/communaute/les-outils-de-la-communaute/autres-services/sentry).)
- **Un projet Sentry de type « Django »**, créé depuis l’interface de Sentry
  (*Projects → Create Project*, plateforme *Django*).
- **Le DSN du projet** : c’est l’adresse à laquelle votre site envoie ses
  rapports. Vous la trouvez dans *Settings → Projects → (votre projet) →
  Client Keys (DSN)*. Elle ressemble à :

  ```text
  https://0123456789abcdef@example.sentry.instance.tld/1234567
  ```

:::{note}
Un même projet Sentry peut recevoir les erreurs de plusieurs instances (par
exemple la production et la recette) : elles sont distinguées grâce à la
variable `SENTRY_ENVIRONMENT`.
:::

## 1. Activer Sentry

Renseignez les variables d’environnement suivantes :

| Variable | Valeur | Obligatoire |
| --- | --- | --- |
| `SENTRY_DSN` | Le DSN copié depuis Sentry | Oui |
| `SENTRY_ENVIRONMENT` | Nom de l’instance : `production`, `recette`, `staging`… | Non (défaut : `production`) |
| `SENTRY_SEND_DEFAULT_PII` | `True` pour joindre des données personnelles aux rapports (voir [Données personnelles](#donnees-personnelles)) | Non (défaut : `False`) |

La façon de les définir dépend de votre mode de déploiement.

### Sur Scalingo

Dans le tableau de bord de votre application, onglet **« Environnement »**,
ajoutez les variables (voir {doc}`scalingo`). Scalingo redémarre
l’application pour prendre en compte les nouveaux réglages.

En ligne de commande, l’équivalent est :

```sh
scalingo --app mon-site env-set \
  SENTRY_DSN="https://0123456789abcdef@example.sentry.instance.tld/1234567" \
  SENTRY_ENVIRONMENT=production
```

### Sur un serveur Linux ou avec Docker

Ajoutez les lignes suivantes au fichier `.env` de votre instance :

```sh
SENTRY_DSN=https://0123456789abcdef@example.sentry.instance.tld/1234567
SENTRY_ENVIRONMENT=production
```

Puis redémarrez l’application, car les réglages ne sont lus qu’au démarrage :

- serveur Linux (voir {doc}`serveur-linux`) :

  ```sh
  sudo systemctl restart sites-conformes
  ```

- Docker (voir {doc}`docker`) :

  ```sh
  docker compose up -d
  ```

## 2. Vérifier que les erreurs remontent

Sites Conformes fournit une page de test qui provoque volontairement une erreur.
Elle est désactivée par défaut.

1. Ajoutez la variable `SENTRY_USE_DEBUG_URL=True` puis redémarrez
   l’application.
2. Ouvrez l’adresse `https://votre-site.gouv.fr/sentry-debug/` dans votre
   navigateur. Une page d’erreur 500 s’affiche : c’est normal.
3. Dans Sentry, ouvrez votre projet, onglet **Issues** : une erreur
   `ZeroDivisionError: division by zero` doit apparaître après quelques secondes.
4. **Supprimez la variable `SENTRY_USE_DEBUG_URL`** (ou remettez-la à `False`)
   puis redémarrez l’application.

:::{important}
**Ne laissez pas `SENTRY_USE_DEBUG_URL` activée.** La page `/sentry-debug/` est
accessible à tout le monde, sans connexion : n’importe qui pourrait l’utiliser
pour générer des erreurs en masse et saturer votre quota Sentry.
:::

Si aucune erreur n’apparaît :

- vérifiez que le DSN est copié **en entier**, sans espace ni guillemet
  superflu ;
- vérifiez que l’application a bien été redémarrée après la modification ;
- vérifiez que votre serveur peut joindre l’adresse de Sentry (un pare-feu ou un
  proxy sortant peut bloquer l’envoi) ;
- vérifiez le filtre d’environnement en haut de l’onglet **Issues** dans Sentry.

## 3. Suivre et traiter les erreurs

Dans Sentry, l’onglet **Issues** regroupe les erreurs identiques en une seule
ligne, avec leur nombre d’occurrences et la date de dernière apparition. Pour
chaque erreur, vous pouvez :

- **consulter le détail** : trace, page concernée, navigateur (et utilisateur
  si `SENTRY_SEND_DEFAULT_PII` est activée) ;
- la marquer comme **résolue** (*Resolve*) une fois corrigée : si elle se
  reproduit, Sentry la rouvre et vous prévient ;
- l’**ignorer** (*Archive*) si elle n’est pas pertinente.

Les **alertes** se règlent dans *Alerts* (par exemple : un e-mail à chaque
nouvelle erreur, ou au-delà d’un certain nombre d’occurrences par heure).
Sentry peut aussi notifier une messagerie d’équipe via ses intégrations.

:::{tip}
Si une erreur semble venir de Sites Conformes lui-même et non de votre contenu
ou de votre configuration, vous pouvez la signaler en
[ouvrant un ticket](https://github.com/numerique-gouv/sites-conformes/issues)
en joignant la trace fournie par Sentry (après en avoir retiré les données
personnelles).
:::

(donnees-personnelles)=

## Données personnelles

Par défaut, Sites Conformes **n’envoie pas de données personnelles** à Sentry :
les rapports ne contiennent ni l’adresse IP du visiteur, ni l’identité de
l’utilisateur connecté, ni les cookies.

Ces informations peuvent toutefois aider à comprendre une erreur (savoir quel
compte l’a rencontrée, par exemple). Pour les joindre aux rapports, ajoutez la
variable :

```sh
SENTRY_SEND_DEFAULT_PII=True
```

Elle active l’option
[`send_default_pii`](https://docs.sentry.io/platforms/python/data-management/data-collected/)
de Sentry : les rapports contiennent alors l’**adresse IP** du visiteur,
l’**identifiant, le nom d’utilisateur et l’adresse e-mail** de l’utilisateur
connecté, ainsi que les **cookies et en-têtes** de la requête.

:::{important}
N’activez cette option qu’en connaissance de cause. Elle constitue un traitement
de données personnelles au sens du RGPD.
:::

Si vous l’activez :

- privilégiez une **instance Sentry hébergée dans l’Union européenne** (instance
  auto-hébergée, instance de votre administration, ou région UE de sentry.io) ;
- **mentionnez ce traitement** dans votre registre des traitements et, si besoin,
  dans les mentions légales ou la politique de confidentialité du site ;
- limitez l’accès au projet Sentry aux seules personnes qui en ont besoin ;
- si nécessaire, masquez certains champs avec les réglages *Security & Privacy →
  Data Scrubbing* du projet Sentry.

## Désactiver Sentry

Supprimez la variable `SENTRY_DSN` (ou laissez-la vide), puis redémarrez
l’application. Plus aucune donnée n’est alors envoyée à Sentry.

## Cas d’une intégration en paquet

Si vous utilisez Sites Conformes comme **paquet** dans votre propre projet Django
(voir {doc}`../paquet/configuration`), l’initialisation de Sentry n’est pas
fournie par le paquet : ajoutez-la dans le `settings.py` de votre projet, par
exemple :

```python
import os

if sentry_dsn := os.getenv("SENTRY_DSN"):
    import sentry_sdk

    sentry_sdk.init(
        dsn=sentry_dsn,
        send_default_pii=getenv_bool("SENTRY_SEND_DEFAULT_PII", False),
        environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
    )
```

La bibliothèque `sentry-sdk[django]` est installée automatiquement avec Sites
Conformes : aucune dépendance supplémentaire n’est nécessaire.

## Pour aller plus loin

- {doc}`Référence des variables d’environnement <variables-environnement>`
- [Documentation officielle de Sentry pour Django](https://docs.sentry.io/platforms/python/integrations/django/)
