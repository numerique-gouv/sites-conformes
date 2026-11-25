"""Lance une fois la mise à jour de la page d'accueil (commande maj_accueil) au déploiement.

La commande se lance d'ordinaire avec `scalingo run`. Cette migration la remplace quand ce n'est pas possible : elle
enregistre un brouillon de l'accueil (rien n'est publié, le menu ne bouge pas) à prévisualiser puis publier dans
Wagtail. Elle n'échoue jamais : si l'accueil a déjà un brouillon ou si le site est vide (nouvelle base, tests), elle
l'écrit dans le journal du déploiement et ne fait rien. Pour la relancer ensuite : python manage.py maj_accueil.

Elle utilise les vrais modèles et non ceux de l'historique des migrations : elle dépend des dernières migrations des
applications concernées, donc le schéma est à jour quand elle tourne.
"""

from django.db import migrations, transaction


def maj_accueil(apps, schema_editor):
    from fabrique import accueil

    try:
        # Point de sauvegarde : une erreur de base ne doit pas laisser la transaction de la migration en échec.
        with transaction.atomic():
            rapport = accueil.run()
    except Exception as e:  # noqa: BLE001 — une erreur ici ne doit pas bloquer le déploiement
        print(f"\n  maj_accueil : rien fait ({e})")
        return
    for ligne in rapport.faits:
        print(f"\n  maj_accueil ✔ {ligne}")
    for ligne in rapport.ignores:
        print(f"\n  maj_accueil ⚠ {ligne}")


class Migration(migrations.Migration):
    dependencies = [
        ("fabrique", "0002_etiquettes_evenement"),
        ("wagtailcore", "0095_groupsitepermission"),
        ("wagtailmenus", "0023_remove_use_specific"),
        ("taggit", "0006_rename_taggeditem_content_type_object_id_taggit_tagg_content_8fc721_idx"),
        ("content_manager", "0001_squashed_0062_catalogindexpage_preview_image_and_more"),
        ("blog", "0001_squashed_0048_blogentrypage_preview_image_and_more"),
        ("events", "0001_squashed_0020_evententrypage_preview_image_and_more"),
    ]

    operations = [migrations.RunPython(maj_accueil, migrations.RunPython.noop, elidable=True)]
