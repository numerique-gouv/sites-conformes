from django.apps import AppConfig


class ProconnectConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"  # type: ignore
    name = "sites_conformes.proconnect"
    label = "sites_conformes_proconnect"

    def ready(self):
        from django.contrib.auth.signals import user_logged_in

        from sites_conformes.proconnect.mfa import record_proconnect_mfa

        user_logged_in.connect(record_proconnect_mfa, dispatch_uid="proconnect_record_mfa")
