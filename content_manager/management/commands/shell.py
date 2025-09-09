from django.core.management.commands import shell


class Command(shell.Command):
    """
    Customize the Django shell to mirror the behaviour of django-extensions' shell_plus command.

    Cf. https://softwarecrafts.uk/100-words/day-275
    """

    def get_auto_imports(self):
        return super().get_auto_imports() + [
            "django.core.cache.cache",
            "django.conf.settings",
            "django.contrib.auth.get_user_model",
            "django.db.transaction",
            "django.db.models.Avg",
            "django.db.models.Case",
            "django.db.models.Count",
            "django.db.models.F",
            "django.db.models.Max",
            "django.db.models.Min",
            "django.db.models.Prefetch",
            "django.db.models.Q",
            "django.db.models.Sum",
            "django.db.models.When",
            "django.utils.timezone",
            "django.urls.reverse",
            "django.db.models.Exists",
            "django.db.models.OuterRef",
            "django.db.models.Subquery",
            # Project-related custom imports
            "content_manager.utils.get_default_site",
        ]
