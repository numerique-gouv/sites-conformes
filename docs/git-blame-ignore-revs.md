# Git blame ignore revs

Le fichier `.git-blame-ignore-revs` liste les commits à exclure de `git blame` — typiquement les PRs de reformatage massif (`black`, `ruff --fix`) qui n'ont pas d'intérêt à être visualisé via un git blame.

## Configuration locale (une fois par clone)

```bash
git config blame.ignoreRevsFile .git-blame-ignore-revs
```

GitHub respecte ce fichier nativement lors d'un `git blame`.

## Ajouter un commit

Récupérer le SHA complet puis l'ajouter au fichier avec un commentaire :

```bash
git rev-parse <short-sha>
```

```sh
# Apply black formatting (2026-02-23)
abc1234def5678abc1234def5678abc1234def5678
```
