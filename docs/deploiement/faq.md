# F.A.Q.

Les problèmes les plus fréquents rencontrés au déploiement et à l'exploitation
d'une instance, et comment s'en sortir.

## Déploiement

### Je n'arrive pas à connecter mon compte GitHub à Scalingo

La connexion se fait depuis l'onglet **« Deploy »** de votre application Scalingo,
section « connexion à un dépôt de code ».

Les causes les plus fréquentes :

- **Vous n'avez pas accès au dépôt.** Sites Conformes ne peut être déployé que
  depuis un dépôt auquel votre compte GitHub a accès. Si ce n'est pas le cas,
  créez un *fork* (copie personnelle gratuite) depuis la
  [page GitHub du projet](https://github.com/numerique-gouv/sites-conformes), puis
  reliez ce fork à Scalingo.
- **Votre organisation GitHub n'a pas autorisé Scalingo.** Si le dépôt appartient
  à une organisation, un·e administrateur·rice doit approuver l'accès de
  l'application Scalingo. Le dépôt n'apparaît pas dans la liste tant que ce n'est
  pas fait.

En cas de blocage, contactez l'équipe à
[contact@sites.beta.gouv.fr](mailto:contact@sites.beta.gouv.fr).

### Le déploiement de mon application échoue

Commencez par lire les journaux, qui indiquent presque toujours la cause exacte.

Depuis le **tableau de bord Scalingo**, dans votre navigateur : ouvrez votre
application et allez dans l'onglet **« Logs »**. Aucun outil à installer.

Ou en ligne de commande, si vous avez le CLI Scalingo :

```bash
scalingo -a mon-site logs --lines 200
```

Les causes classiques, par ordre de fréquence :

- **`SECRET_KEY` absente** — le site ne démarre pas tant qu'elle n'est pas
  renseignée. C'est normal lors d'un tout premier déploiement : voir la question
  ci-dessous.
- **Pas de base de données** — vérifiez que l'addon PostgreSQL est bien ajouté et
  que `DATABASE_URL` est renseignée (Scalingo la remplit automatiquement).
- **`HOST_URL` mal formée** — elle doit contenir **le nom de domaine seul**, sans
  `https://` ni numéro de port. L'application refuse explicitement de démarrer
  sinon.
- **`ALLOWED_HOSTS` ne contient pas votre domaine** — voir plus bas.

> ⏱️ **Cas connu : le timeout du post-déploiement Scalingo.** Au tout premier
> lancement d'une instance, la phase de post-déploiement (migrations, création
> des pages de démarrage, indexation) est longue et peut dépasser le temps
> maximum accordé par Scalingo : elle est alors interrompue en cours de route.
>
> Ce n'est **pas bloquant** : relancez simplement le déploiement — il faut
> généralement **2 à 3 relances** pour que l'ensemble passe. Les commandes sont
> conçues pour être rejouables et chaque exécution reprend là où la précédente
> s'est arrêtée, jusqu'à ce que toutes les migrations soient passées. Nous avons
> connaissance de ce comportement.

### Je ne parviens pas à générer ma `SECRET_KEY`

La commande à lancer via le CLI Scalingo, en remplaçant `mon-site` par le nom de
votre application :

```bash
scalingo -a mon-site run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copiez la valeur affichée dans la variable `SECRET_KEY` (onglet « Environnement »).

> 🔑 **N'utilisez pas un générateur de mot de passe trouvé en ligne** : vous ne
> savez pas si le site en conserve une copie, ce qui compromettrait la sécurité de
> votre site.

Si vous ne pouvez pas installer le CLI, demandez à un collègue technique de
générer la clé sur sa machine — n'importe quel environnement Python avec Django
installé suffit.

### Je ne parviens pas à récupérer la dernière mise à jour

Deux cas :

- **Votre application est reliée à un *fork*.** Scalingo déploie le code de
  *votre* copie, pas celui du dépôt officiel. Tant que le fork n'est pas
  synchronisé, aucune nouvelle version n'arrive, même avec le déploiement
  automatique activé. Sur la page GitHub de votre fork, utilisez le bouton
  **« Sync fork »**, puis relancez un déploiement si nécessaire.
- **Le déploiement automatique n'est pas activé.** Rendez-vous dans l'onglet
  « Deploy » et relancez manuellement un déploiement.

Vérifiez également que vous déployez bien la branche **`production`** (la version
stable) et non `main` (les développements en cours).

## Configuration

### Une de mes variables d'environnement est incorrecte

Corrigez-la dans l'onglet **« Environnement »** de Scalingo (ou dans le fichier
`.env` sur un serveur autogéré), puis **redémarrez l'application** : les variables
ne sont lues qu'au démarrage.

Le rôle, la valeur par défaut et le caractère obligatoire de chaque réglage sont
détaillés dans {doc}`variables-environnement`.

### Le site répond « DisallowedHost » ou une erreur 400

Le domaine utilisé pour accéder au site n'est pas déclaré dans `ALLOWED_HOSTS`.
Ajoutez-le à la liste, séparé par des virgules s'il y en a plusieurs, puis
redémarrez.

Pensez à y mettre **tous** les domaines par lesquels le site est joignable
(l'adresse de test Scalingo *et* le domaine définitif, par exemple).

### Où se trouve l'administration du site ?

À l'adresse de votre site suivie de **`/cms-admin/`** par défaut. Ce chemin est
configurable via la variable `WAGTAILADMIN_PATH`.

## Contenus et affichage

### Les images ont disparu après un déploiement

C'est le symptôme d'un **stockage des médias sur le disque de l'application**.
Sur un PaaS comme Scalingo, le système de fichiers est éphémère : il est
réinitialisé à chaque déploiement, emportant les fichiers téléversés.

La solution est de configurer un **stockage objet S3**, qui conserve les fichiers
en dehors de l'application. Voir la section « Paramètres pour le stockage objet »
de la page {doc}`scalingo`.

> ⚠️ Les images déjà perdues ne sont pas récupérables : il faut les téléverser à
> nouveau une fois le S3 en place.

### Le site s'affiche sans mise en forme (CSS absent)

Les fichiers statiques n'ont pas été collectés ou ne sont pas servis :

```bash
python manage.py collectstatic --noinput --ignore="*.sass"
```

Si aucun serveur web dédié ne sert le dossier des statiques, activez
`SF_USE_WHITENOISE=1` pour que l'application les serve elle-même.

### La recherche ne renvoie aucun résultat

L'index de recherche doit être reconstruit :

```bash
python manage.py update_index
```

Sur Scalingo, cette commande est lancée **automatiquement après chaque
déploiement**. Sur un serveur autogéré, il est recommandé de la programmer une
fois par semaine (voir {doc}`serveur-linux`).

Un index vide est également normal juste après l'import d'une base de données :
l'index n'est pas transféré avec les données.

### Le site pointe encore vers l'ancien domaine après une migration

Le nom de domaine est stocké **à deux endroits** : dans les variables
d'environnement et dans la base de données. Après avoir mis à jour `HOST_URL`,
répercutez-le en base :

```bash
python manage.py set_config
```

Voir {doc}`migrer-hebergement` pour la procédure complète.

### Les e-mails ne partent pas

L'envoi d'e-mails n'est activé que si **`DEFAULT_FROM_EMAIL` est renseignée**. Si
cette variable est vide, tous les autres réglages e-mail (`EMAIL_HOST`,
`EMAIL_PORT`, etc.) sont ignorés, sans message d'erreur.

Vérifiez donc d'abord cette variable, puis les paramètres SMTP fournis par votre
service informatique. La liste complète figure dans {doc}`variables-environnement`.

---

Votre question n'est pas ici ? Écrivez à
[contact@sites.beta.gouv.fr](mailto:contact@sites.beta.gouv.fr) ou passez sur le
[salon Tchap](https://www.tchap.gouv.fr/#/room/#sites-faciles:agent.dinum.tchap.gouv.fr).
