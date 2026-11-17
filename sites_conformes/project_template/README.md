# {{ project_name }}

Site créé avec [Sites Conformes][sc] {{ sites_conformes_version }}.

[sc]: https://github.com/numerique-gouv/sites-conformes

## Démarrer

```sh
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
uv run python manage.py create_starter_pages
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Le site est sur <http://localhost:8000/>, l’administration sur
<http://localhost:8000/cms-admin/>. `collectstatic` doit précéder
`create_starter_pages`, qui y lit les pictogrammes.

## Configurer

Les réglages sont dans `config/settings.py`. Ceux qui changent d’un
environnement à l’autre se lisent dans le fichier `.env` (non versionné) :

| Variable | Rôle |
| --- | --- |
| `SECRET_KEY` | Clé secrète de Django, générée à la création du projet |
| `DEBUG` | `True` en développement, à retirer en production |
| `DATABASE_URL` | Base PostgreSQL (`postgres://…`). Sans elle, le site utilise SQLite |
| `ALLOWED_HOSTS`, `HOST_URL` | Nom de domaine du site en production |
