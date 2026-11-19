from django.apps import AppConfig


class FabriqueConfig(AppConfig):
    """Personnalisations propres au site de la Fabrique de la donnée territoriale.

    Rassemblées dans une application séparée pour ne pas toucher au code de
    Sites Faciles et faciliter les montées de version.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "fabrique"
    verbose_name = "Fabrique de la donnée territoriale"
