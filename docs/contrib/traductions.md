# Traductions

Le projet utilise le [système de traduction de Django](https://docs.djangoproject.com/en/dev/topics/i18n/translation/).

Le texte dans le code est en anglais ; la traduction qui s’affiche sur le site, en français, se trouve dans le fichier
`.po` du dossier `locale`.

## Générer les traductions

Pour mettre à jour le fichier `.po` avec les chaînes à traduire :

```sh
just makemessages
```

Django utilise une version compilée du fichier `.po` — le fichier `.mo` — que l’on obtient avec :

```sh
uv run python manage.py compilemessages
```

## Poedit

Il est recommandé d’utiliser [Poedit](https://poedit.net/) pour les traductions, afin de profiter de sa mémoire de traduction
basée sur celles déjà existantes. Il produit directement le fichier `.mo` à la sauvegarde : il n’est alors pas nécessaire de le
compiler manuellement.
