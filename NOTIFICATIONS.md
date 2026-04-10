# 📢 Comment modifier les notifications

## À propos du fichier `notifications.json`

Ce fichier est consommé par le panneau d'information de l'admin Sites Conformes. Il permet d'envoyer des notifications sur les différents back-office.

> 💡 Une notification est également envoyée automatiquement si la version installée n'est pas la même que la dernière version publiée.

---

## Guide de modification

Ce guide explique comment ajouter, modifier ou désactiver une notification directement depuis GitHub, sans avoir besoin d'installer quoi que ce soit.

---

## 📋 Les types de notifications

Il existe 3 types de notifications :

| Type | Design |
|------|-------|
| `info` | Le fond s'affiche en bleu et l'icône est un "i" (voir DSFR) |
| `alert` | Le fond s'affiche en rouge et l'icône est point d'exclammation dans un rond rouge (voir DSFR) |
| `warning` | Le fond s'affiche en orange et l'icône est un point d'exclammation dans un triangle (voir DSFR)  |

---

## ✏️ Modifier le fichier

### Étape 1 — Ouvrir le fichier

1. Aller sur le dépôt GitHub du projet
2. Cliquer sur le fichier **`notifications.json`**


### Étape 2 — Passer en mode édition

Cliquer sur l'icône **✏️ crayon** en haut à droite du fichier.

> Si le crayon n'est pas visible, il est possible que les droits d'édition ne soient pas attribués. Contacter l'équipe technique.

### Étape 3 — Effectuer la modification

Le fichier ressemble à ceci :

```json
{
    "items": [
        {
            "type": "info",
            "title": "Ma nouveauté",
            "description": "Description courte.",
            "url": "https://lien-vers-plus-info.fr",
            "date": "2026-04-01",
            "end_date": "2026-04-30"
        }
    ]
}
```

Chaque notification est un **bloc entre `{` et `}`**, séparé des autres par une virgule.

### Étape 4 — Proposer les changements (Pull Request)

1. En bas de la page, dans la section **"Commit changes"**, remplacer le message par défaut par quelque chose de clair, par exemple :
   > `Ajout notification maintenance 15 mai`
2. Sélectionner **"Create a new branch and start a pull request"**
3. Cliquer sur **"Propose changes"**
4. Sur la page suivante, cliquer sur **"Create pull request"**

> ⚠️ Ne pas cliquer sur "Commit directly to the `main` branch" — cela court-circuiterait la vérification automatique.

### Étape 5 — Attendre la vérification

Une vérification automatique se lance. En bas de la Pull Request, on peut voir :

- ✅ **Checks passed** → tout est bon, l'équipe technique peut valider
- ❌ **Checks failed** → il y a une erreur dans le fichier (voir section [En cas d'erreur](#-en-cas-derreur))

---

## 📝 Exemples concrets

### Ajouter une nouvelle notification

Copier un bloc existant et le modifier. Ne pas oublier la **virgule** entre chaque bloc :

```json
{
    "items": [
        {
            "type": "info",
            "title": "Nouvelle fonctionnalité : exports CSV",
            "description": "Vous pouvez désormais exporter vos données en CSV.",
            "url": "https://docs.monsite.fr/exports",
            "date": "2026-05-01",
            "end_date": "2026-05-31"
        },
        {
            "type": "alert",
            "title": "Maintenance le 15 mai",
            "description": "Le service sera indisponible de 22h à 23h.",
            "url": "",
            "date": "",
            "end_date": "2026-05-15"
        }
    ]
}
```

### Désactiver une notification sans la supprimer

Modifier la `end_date` pour une date **dans le passé** :

```json
"end_date": "2020-01-01"
```

---

## 📌 Règles importantes

| Champ | Obligatoire | Format | Peut être vide |
|-------|-------------|--------|----------------|
| `type` | ✅ | `info`, `alert` ou `warning` | ❌ |
| `title` | ✅ | Texte libre | ❌ |
| `description` | ✅ | Texte libre | ✅ |
| `url` | ✅ | URL complète (`https://...`) | ✅ |
| `date` | ✅ | `YYYY-MM-DD` (ex: `2026-05-01`) | ✅ |
| `end_date` | ✅ | `YYYY-MM-DD` (ex: `2026-05-31`) | ✅ |

> 💡 **Les templates en haut du fichier** (ceux avec "à ne pas supprimer") servent d'exemples. Ne pas les supprimer, mais s'en inspirer pour créer de nouvelles notifications.

---

## 🚨 En cas d'erreur

Si la vérification échoue, cliquer sur **"Details"** à côté de la croix rouge. Le message d'erreur indique précisément le problème, par exemple :

| Message | Cause probable |
|---------|----------------|
| `'type' is a required property` | Le champ `type` est manquant |
| `'warning' is not valid` | Valeur incorrecte pour `type` (vérifier l'orthographe) |
| `'end_date' does not match pattern` | Format de date incorrect (utiliser `YYYY-MM-DD`) |
| `Additional properties are not allowed` | Un champ inconnu a été ajouté (ex: faute de frappe dans un nom de champ) |

En cas de doute, contacte l'équipe technique en mentionnant le message d'erreur.

---

## ❓ Questions fréquentes

**La notification n'apparaît plus, mais la date de fin n'est pas passée ?**
Vérifier que la `date` de début n'est pas dans le futur.

**Comment rendre une notification permanente ?**
Mettre une `end_date` très lointaine, par exemple `2099-12-31`.

**Est-il possible d'ajouter autant de notifications que souhaité ?**
Oui, mais il est conseillé d'en garder un nombre raisonnable pour ne pas surcharger les utilisateurs.
