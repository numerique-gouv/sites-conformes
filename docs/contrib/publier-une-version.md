# Publier une version

Sites Conformes est publié sur [PyPI](https://pypi.org/project/sites-conformes/)
sous le nom `sites-conformes`, et sous forme d’image Docker sur
`ghcr.io/numerique-gouv/sites-conformes`. Les deux publications partent d’une
*release* GitHub.

## Numérotation

Les numéros de version suivent la [PEP 440](https://peps.python.org/pep-0440/) :

- `X.Y.Z` pour une version stable (`4.4.0`) ;
- `X.Y.ZrcN` pour une pré-version pour *release candidate* (`4.4.0rc1`).

Le tag Git est le numéro de version précédé d’un `v` (`v4.4.0`, `v4.4.0rc1`).
Le numéro est défini dans `sites_conformes/_version.py`, qui doit correspondre
au tag : au moment de la publication sur PyPI, le workflow réécrit ce fichier à
partir du tag. En revanche, les déploiements faits depuis les sources
(Scalingo, serveur interne, image Docker) lisent directement la valeur
committée.

## Publier une version stable

1. Lancer `just test-release`, qui contient des tests supplémentaires.
2. Passer `__version__` à `X.Y.Z` dans `sites_conformes/_version.py`. Si la
   version demande une action de l’opérateur (migration, gel des
   contributions…), l’ajouter à `docs/changelog.md`.
3. Faire intégrer ces changements dans `main`.
4. Créer une *release* GitHub sur `main`, avec le tag `vX.Y.Z` et les notes
   de version en français.

La publication de la *release* déclenche :

- `.github/workflows/publish.yml`, qui construit le paquet et le publie sur
  PyPI ;
- `.github/workflows/cd-docker.yml`, qui publie les images `:X.Y.Z` et
  `:latest`.

## Publier une pré-version

Une pré-version permet de faire tester une version avant de la rendre
disponible à tous. La procédure est la même que pour une version stable, avec
deux différences :

- `_version.py` et le tag portent le suffixe de pré-version (`4.4.0rc1`,
  tag `v4.4.0rc1`) ;
- dans le formulaire de la *release* GitHub, cocher « Set as a pre-release ».

PyPI la signale comme pré-version, et ni `pip` ni `uv` ne l’installent par
défaut. Côté Docker, l’image `:4.4.0rc1` est publiée, mais `:latest` ne bouge
pas.

Pour publier une nouvelle pré-version, incrémenter le suffixe (`rc2`). Pour la
version finale, repasser `_version.py` à `4.4.0` et publier une version
stable.

Cette pré-version est installée sur les instances de l'équipe Sites Conformes et
testée pendant une semaine avant publication définitive.

## Installer une pré-version

Dans le projet qui utilise le paquet, il faut demander explicitement la
pré-version :

```bash
# pip
pip install "sites-conformes==4.4.0rc1"
pip install --pre sites-conformes   # dernière version, pré-versions comprises

# uv
uv add "sites-conformes==4.4.0rc1"
uv add --prerelease=allow sites-conformes
```

Si le projet hôte définit un délai de carence (`exclude-newer` dans la section
`[tool.uv]`), une pré-version publiée trop récemment reste invisible tant que
ce délai n’est pas écoulé.

## En cas d’échec

Le paquet n’est envoyé sur PyPI qu’une fois la construction réussie (job
`build`). Si le workflow échoue avant cette étape, rien n’a été publié :

1. corriger le problème et faire intégrer le correctif dans `main` ;
2. relancer « Publish to PyPI » depuis l’onglet *Actions* (`workflow_dispatch`),
   sur `main`, en saisissant la version (par exemple `4.4.0rc1`).

L’option `skip-existing` empêche de publier deux fois la même version : un
numéro déjà envoyé sur PyPI ne peut pas être remplacé. Pour corriger une
version déjà publiée, il faut publier un nouveau numéro.

Autre possibilité : supprimer la *release* et son tag, puis les recréer sur
le commit qui contient le correctif. Cela relance aussi l’image Docker.

Avant d’intégrer le correctif, on peut vérifier en local que les traductions
compilées sont bien embarquées dans le paquet :

```bash
just compilemessages
uv build --wheel --out-dir /tmp/sites-conformes-dist
unzip -Z1 /tmp/sites-conformes-dist/*.whl | grep '\.mo$'
```
