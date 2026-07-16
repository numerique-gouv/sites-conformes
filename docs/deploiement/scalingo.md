# Sur Scalingo (ou PaaS) — 🟢 Débutant

Scalingo est le PaaS (Platform as a Service) utilisé par la DINUM pour déployer Sites Conformes. **C'est la méthode la plus simple et la plus documentée**, recommandée si vous n'avez pas d'équipe d'administration système : la plateforme gère elle-même le serveur web, le système d'exploitation, les mises à jour de sécurité de l'infrastructure, etc.

> 💡 **C'est quoi un PaaS ?** Le sigle veut dire « Platform as a Service » (plateforme en tant que service). Concrètement, c'est un site web sur lequel vous déposez votre application, et qui s'occupe de tout le reste (le serveur, sa sécurité, sa maintenance) à votre place. Vous travaillez depuis votre navigateur, sans jamais gérer de serveur vous-même.

> ℹ️ **Une étape demande un petit outil à installer.** La quasi-totalité des étapes se fait depuis le site de Scalingo, dans votre navigateur. **Une seule étape** (l'initialisation du site, étape 4) nécessite un petit logiciel gratuit appelé « CLI Scalingo ». Pas d'inquiétude : la marche à suivre est détaillée le moment venu, et si vous travaillez avec un collègue technique, c'est l'étape idéale à lui confier.

## Prérequis

- Un compte Scalingo
- **Un compte GitHub** ayant accès au code de Sites Conformes (pour le récupérer). Rapprochez-vous de l'équipe Sites Conformes pour cette étape qui vous indiquera la marche à suivre (récupérer l'accès au répertoire GitHub ou créer un *fork*).
- **Un espace de stockage S3** (voir l'encart ci-dessous). Ce n'est pas indispensable pour le tout premier essai, mais le deviendra dès que vous ajouterez des images.
- Le [CLI Scalingo](https://doc.scalingo.com/platform/cli/start) installé en local.

> 💡 **C'est quoi un stockage S3 ?** C'est un espace en ligne, chez un autre prestataire (OVH ou CleverCloud par exemple), où sont rangées les images et les documents que vous mettrez sur votre site. Sur Scalingo, ces fichiers ne peuvent pas rester sur le serveur du site : sans S3, les images ajoutées disparaîtraient à la prochaine mise à jour. On le configure à l'étape 2c.

## Étape 1 — Créer l'application et sa base de données

Tout se passe dans votre navigateur, sur le tableau de bord Scalingo.

1. Connectez-vous à votre espace/tableau de bord Scalingo.
2. Cliquez sur « créez une app » et donnez-lui un nom (par exemple `mon-site`). Ce nom servira aussi d'adresse de test, du type `mon-site.osc-fr1.scalingo.io`.
3. Une fois l'application créée, ajoutez-lui une base de données : dans le menu de l'app, allez dans **« Addons »** (modules complémentaires), choisissez **PostgreSQL**, puis l'offre **Starter – 512 Mo** (suffisante pour démarrer).

> 💡 **C'est quoi une base de données ?** C'est l'endroit où votre site range toutes ses informations (les pages que vous créez, les comptes, les réglages). PostgreSQL est le type de base de données utilisé par Sites Conformes. Sur Scalingo, l'ajouter est aussi simple que d'activer une option.

> 💡 **C'est quoi un « addon » ?** Un service supplémentaire que l'on branche à son application en quelques clics, ici la base de données.

> 💡 **Quelle configuration pour mon app ?** Si le site a très peu de trafic (notamment pendant la période de création/rédaction avant mise en production), un petit serveur suffit : sur Scalingo, Sites Conformes peut être déployé sur les configurations les plus petites, en l'occurrence un [container taille S](https://doc.scalingo.com/platform/internals/container-sizes) et une base de données PostgreSQL [Starter - 512 Mo](https://scalingo.com/fr/databases/postgresql).

## Étape 2 — Renseigner les réglages (variables d'environnement)

> 💡 **C'est quoi une « variable d'environnement » ?** C'est un réglage que l'on donne à l'application sous forme de **nom + valeur**. Par exemple, le réglage nommé `HOST_URL` reçoit comme valeur l'adresse de votre site. L'application lit ces réglages au démarrage pour savoir comment se comporter.

Les variables d'environnement se configurent depuis le tableau de bord de votre application Scalingo, dans l'onglet **« Environnement »**. Vous y verrez deux colonnes, une pour le **nom** du réglage et une pour sa **valeur**. Pour chaque ligne du tableau ci-dessous, vous créez une entrée, vous tapez le nom à gauche et la valeur à droite, puis vous enregistrez.

> 🔗 Liste complète de référence : tous les réglages possibles sont listés dans [le fichier `.env.example`](https://github.com/numerique-gouv/sites-conformes/blob/main/.env.example) du dépôt de Sites Conformes, et décrits un par un dans la {doc}`référence des variables d'environnement <variables-environnement>`. Vous n'avez pas à le copier : il sert juste de référence si vous cherchez le nom exact d'un réglage ou sa valeur par défaut.

> 🧭 **Tous les réglages ne sont pas obligatoires.** Pour un premier déploiement, seule la partie **a** ci-dessous est nécessaire. Les parties b, c et d s'ajoutent plus tard, selon vos besoins.
> Pour s'y retrouver :
> 🔴 **INDISPENSABLE** : sans ce réglage, le site ne démarre pas.
> 🟠 **RECOMMANDÉ** : nécessaire pour un site complet (e-mails, images), mais pas pour un premier essai.
> ⚪ **OPTIONNEL** : seulement si vous avez un besoin précis.

### a. Réglages principaux — 🔴 INDISPENSABLE

Créez ces réglages. Le tableau indique exactement quoi taper dans la colonne « valeur » :

| Nom du réglage (à gauche) | Valeur à taper (à droite) ou exemple | À quoi ça sert ? |
| --- | --- | --- |
| 🔴 `HOST_URL` | Exemple : `test-sites-faciles.osc-fr1.scalingo.io` | le nom de domaine de l'URL principale de votre site |
| 🔴 `ALLOWED_HOSTS` | Exemple : `test-sites-faciles.osc-fr1.scalingo.io,test-sites-faciles.numerique.gouv.fr` | le ou les domaines autorisés à accéder au site, séparés par des virgules s'il y en a plusieurs. On peut déjà entrer le domaine définitif si on le connaît |
| 🔴 `SECRET_KEY` | *(voir encart ci-dessous)* | clé secrète, par exemple générée dans un terminal (rapprochez-vous d'un utilisateur technique pour cette étape) |
| 🔴 `DATABASE_URL` | *(rempli automatiquement)* | Ce paramètre a normalement été rempli automatiquement par Scalingo à l'étape 1, vérifiez que c'est bien le cas |

> 🔑 **Comment obtenir la valeur de `SECRET_KEY` ?** Cette clé protège les connexions et les mots de passe de votre site. Elle doit rester secrète et être **vraiment** tirée au hasard. **N'utilisez pas un générateur de mot de passe trouvé sur internet** : vous ne savez pas si le site garde une copie de votre clé, ce qui compromettrait la sécurité de votre site.
> La façon sûre de l'obtenir est de la faire fabriquer par votre application elle-même, à l'étape 4 (qui utilise le petit outil « CLI »). En attendant, vous pouvez :
> - soit demander à un collègue technique de vous fournir une clé générée sur sa machine ;
> - soit revenir remplir ce réglage juste après l'étape 4, en utilisant la commande indiquée là-bas.
>
> Tant que `SECRET_KEY` n'est pas renseignée, le site ne démarrera pas — c'est normal, vous la remplirez à l'étape 4.

### b. Réglages pour l'envoi d'e-mails — 🟠 RECOMMANDÉ

Ces réglages permettent au site d'envoyer des e-mails (réinitialisation de mot de passe, notification quand un formulaire est rempli).

Vous pouvez les laisser de côté pour un premier essai et y revenir ensuite.

Vous aurez besoin des informations de connexion d'un service d'envoi d'e-mails (fournies par votre service informatique ou un prestataire).

| Nom du réglage (à gauche) | Valeur à taper (à droite) ou exemple | À quoi ça sert ? |
| --- | --- | --- |
| `DEFAULT_FROM_EMAIL` | | L'adresse qui apparaîtra comme expéditeur des e-mails.<br>Si ce réglage est absent ou vide, le reste des réglages concernant les e-mails sera ignoré. |
| `EMAIL_HOST` | | L'adresse du serveur d'envoi (fournie par votre prestataire e-mail) |
| `EMAIL_PORT` | | le port à utiliser pour le serveur SMTP défini dans le paramètre précédent |
| `EMAIL_HOST_USER` | | le nom d'utilisateur à utiliser pour le serveur SMTP défini dans `EMAIL_HOST`. S'il est vide, Django ne tente pas de s'authentifier. |
| `EMAIL_HOST_PASSWORD` | | le mot de passe du compte défini dans le paramètre précédent |
| `EMAIL_USE_TLS` | `True` (recommandé) / `False` | indique si une connexion TLS (sécurisée) doit être utilisée pour le dialogue avec le serveur SMTP |
| `EMAIL_USE_SSL` | `True` / `False` | indique si une connexion TLS implicite (sécurisée) doit être utilisée pour le dialogue avec le serveur SMTP |
| `EMAIL_TIMEOUT` | `30` (ne doit pas être mis à 0 !) | définit un délai d'expiration en secondes pour des opérations bloquantes telles que la tentative de connexion |
| `EMAIL_SSL_KEYFILE` | | si `EMAIL_USE_SSL` ou `EMAIL_USE_TLS` valent `True`, vous pouvez définir de manière facultative le chemin vers un fichier de clé privée de type PEM à utiliser pour la connexion SSL |
| `WAGTAIL_PASSWORD_RESET_ENABLED` | `True` | active le lien « mot de passe oublié » |

> 💡 Ces réglages très techniques sont généralement fournis clés en main par votre service informatique ou votre prestataire de messagerie. Recopiez simplement les valeurs qu'ils vous donnent.

Voir aussi les documentations de [Django](https://docs.djangoproject.com/fr/5.0/topics/email/) et [Wagtail](https://docs.wagtail.org/en/stable/reference/settings.html#wagtail-password-reset-enabled).

### c. Paramètres pour le stockage objet — 🟠 RECOMMANDÉ

À configurer dès que vous commencez à ajouter des images ou des documents au site (sinon ils disparaîtraient à la mise à jour suivante). Il vous faut d'abord un espace S3 chez un prestataire (OVH, CleverCloud…), qui vous fournira les cinq informations ci-dessous.

- Configurez un object storage S3, chez CleverCloud ou OVH par exemple.
- Ajoutez les variables d'environnement suivantes à votre application Scalingo :

| Nom du réglage (à gauche) | Valeur à taper (à droite) ou exemple | À quoi ça sert ? |
| --- | --- | --- |
| `S3_BUCKET_NAME` | généralement le nom de l'app — fournie par votre prestataire | Le nom de votre espace de stockage |
| `S3_BUCKET_REGION` | `eu-west-3` — fournie par votre prestataire | La région indiquée par votre prestataire |
| `S3_HOST` | fournie par votre prestataire | L'adresse du service, **sans** `https://` |
| `S3_KEY_ID` | clé d'identifiant unique — fournie par votre prestataire | L'identifiant d'accès fourni par le prestataire |
| `S3_KEY_SECRET` | clé secrète — fournie par votre prestataire | La clé secrète d'accès fournie par le prestataire |
| ⚪ `S3_LOCATION` | | optionnel, permet de partager un même S3 pour plusieurs sites |

> 💡 **C'est quoi un « bucket » ?** C'est simplement le nom technique d'un espace de rangement S3 (littéralement un « seau »). Votre prestataire vous fait en créer un et vous donne son nom et deux clés d'accès, que vous recopiez ici.

Le paramètre `S3_LOCATION` est optionnel mais permet de partager le bucket S3 avec plusieurs installations de Sites Conformes. Il est recommandé d'utiliser le nom de l'app comme valeur (ici `test-sites-faciles`).

Une alternative au S3 est le stockage des médias directement en base PostgreSQL : voir {doc}`../donnees/stockage-medias`.

### d. Paramètres supplémentaires — ⚪ OPTIONNEL

À ne toucher que si vous avez un besoin particulier ; sinon, ignorez cette partie.

| Nom du réglage (à gauche) | Valeur à taper (à droite) ou exemple | À quoi ça sert ? |
| --- | --- | --- |
| `WAGTAILADMIN_PATH` | par défaut : `cms-admin/` | permet de définir l'adresse d'accès au back-office |
| `SF_USE_WHITENOISE` | par défaut : `0` (False) / `1` (True) | active ou non l'usage de WhiteNoise, laisser tel quel sauf cas spéciaux |
| `SF_DISABLE_TUTORIALS` | par défaut : `True` | permet de désactiver le panel des tutoriels sur la page d'accueil du back-office |
| `PROCONNECT_ACTIVATED` | par défaut : `False` | active ProConnect |

## Étape 3 — Récupérer le code du site

Toujours dans votre navigateur, sur le tableau de bord de votre app :

1. Ouvrez l'onglet **« Deploy »** (déploiement).
2. Dans la partie « connexion à un dépôt de code », reliez votre compte **GitHub**, puis sélectionnez le dépôt de Sites Conformes.
3. Choisissez la branche à déployer : `production` (c'est la version stable, prévue pour les sites en service).
4. Lancez le déploiement.

> ⚠️ **Si vous n'avez pas accès au dépôt** : créez-en une copie personnelle gratuite en cliquant sur « Fork » sur la [page GitHub du projet](https://github.com/numerique-gouv/sites-conformes), puis reliez cette copie à Scalingo. Un « fork » est simplement votre exemplaire personnel du code. **Attention** : pour bénéficier régulièrement des mises à jour, il est nécessaire de mettre à jour votre fork en même temps que le code source de Sites Conformes.

> 💡 **C'est quoi un « dépôt » et une « branche » ?** Le *dépôt* est l'endroit où est rangé le code du logiciel Sites Conformes (sur GitHub). Une *branche* est une version de ce code : la branche `production` est la version finie et testée, celle qu'on installe pour un vrai site.

## Étape 4 — Mettre le site en route (initialisation)

C'est la seule étape qui demande le petit outil « CLI Scalingo ». Elle ne se fait qu'**une fois**, à la première installation.

> 💡 **C'est quoi le « CLI » ?** Le sigle signifie « Command Line Interface » (interface en ligne de commande). C'est un petit logiciel gratuit que vous installez sur votre ordinateur, et dans lequel vous tapez des commandes pour piloter votre application Scalingo. Pour cette étape, vous n'aurez qu'à **copier-coller** les commandes ci-dessous, sans rien avoir à comprendre ni inventer.

> 🤝 **Vous préférez ne pas toucher au terminal ?** Cette étape est la candidate idéale à confier à un collègue technique, à votre service informatique, ou à l'équipe de Sites Conformes. Une fois faite, vous reprenez la main entièrement dans le navigateur.

**a. Installer le CLI** en suivant la page officielle (instructions pour Windows, Mac et Linux) : <https://doc.scalingo.com/platform/cli/start>. Vous vous y connecterez ensuite avec votre compte Scalingo.

**b. Générer la clé secrète** (celle de l'étape 2a) en copiant-collant cette commande, après avoir remplacé `mon-site` par le nom de votre application :

```bash
scalingo -a mon-site run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Une longue suite de 50 caractères s'affiche : copiez-la, retournez dans l'onglet « Environment » (étape 2) et collez-la comme valeur de `SECRET_KEY`.

**c. Créer votre compte administrateur** (celui qui vous permettra de vous connecter pour gérer le site) :

```bash
APP_NAME=test-sites-faciles
scalingo -a ${APP_NAME} run python manage.py createsuperuser
```

L'outil vous demandera de choisir un identifiant et un mot de passe. Notez-les soigneusement : ce sont vos accès à l'administration du site.

Initialiser le contenu du site en faisant passer ces commandes via la CLI Scalingo :

```bash
scalingo -a ${APP_NAME} run python manage.py migrate
scalingo -a ${APP_NAME} run python manage.py collectstatic --noinput --ignore="*.sass"
scalingo -a ${APP_NAME} run python manage.py set_config
scalingo -a ${APP_NAME} run python manage.py import_dsfr_pictograms
scalingo -a ${APP_NAME} run python manage.py create_starter_pages
```

> 💡 **Et les autres commandes de mise en route ?** Le remplissage initial du site (création des premières pages, préparation de la recherche, etc.) est lancé **automatiquement** par Scalingo après chaque déploiement. Vous n'avez donc normalement que les commandes ci-dessus à exécuter vous-même. Si jamais une commande devait être relancée manuellement, elle se présenterait sous la même forme : `scalingo -a mon-site run python manage.py <nom-de-la-commande>`.

Votre site est maintenant en ligne à l'adresse définie dans `HOST_URL`, et son administration est accessible (par défaut à l'adresse de votre site suivie de `/cms-admin/`).

## Mise à jour

La mise à jour est presque entièrement automatique et se fait dans le navigateur.

- **Si le déploiement automatique est activé** (le plus courant : la branche `production` est reliée à votre app), il n'y a **rien à faire** : à chaque nouvelle version du logiciel, Scalingo redéploie tout seul et lance automatiquement les opérations techniques nécessaires.

> ⚠️ **Si votre app est reliée à un fork** (une copie personnelle du dépôt officiel, voir l'étape 3), pensez à **mettre ce fork à jour régulièrement** depuis GitHub. Scalingo déploie le code de *votre* fork, pas celui du dépôt officiel : tant que le fork n'est pas synchronisé, vous ne recevez aucune nouvelle version, même avec le déploiement automatique activé. Sur la page GitHub de votre fork, le bouton **« Sync fork »** récupère les dernières modifications du dépôt d'origine ; le déploiement Scalingo se déclenche ensuite (automatiquement ou manuellement selon votre réglage).

- **Si le déploiement est manuel** : retournez dans l'onglet **« Deploy »** et cliquez pour relancer un déploiement de la branche `production`.

> 💡 **Et mes données pendant la mise à jour ?** Vos contenus (pages, images, comptes) sont conservés : ils sont rangés dans la base de données et le stockage S3, qui ne sont pas touchés par une mise à jour du code.

> 💾 **Sauvegardes** : sur Scalingo, la base de données PostgreSQL est sauvegardée automatiquement par la plateforme. Vous pouvez consulter et télécharger ces sauvegardes depuis l'interface de l'addon PostgreSQL, dans votre navigateur. Voir aussi {doc}`../donnees/sauvegarde-restauration`.
