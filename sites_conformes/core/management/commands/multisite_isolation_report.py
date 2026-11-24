from django.core.management.base import BaseCommand

from sites_conformes.core.multisite_isolation import (
    get_groups_without_site,
    get_site_scoped_models,
    is_multisite_isolation_active,
)


class Command(BaseCommand):
    help = (
        "Lists the groups that have permissions on site-scoped models (menus, etc.) but no page permission: "
        "with the multisite isolation enabled, their members lose access to these models."
    )

    def handle(self, *args, **options):
        """
        Prints the state of the isolation, the site-scoped models and the groups without page permission.
        """
        state = "enabled" if is_multisite_isolation_active() else "disabled"
        self.stdout.write(f"Multisite isolation: {state}")

        models = get_site_scoped_models()
        self.stdout.write("Site-scoped models: " + ", ".join(model._meta.label for model in models))

        groups = get_groups_without_site(models)
        if not groups:
            self.stdout.write(self.style.SUCCESS("Every group with permissions on these models has page permissions."))
            return

        self.stdout.write(self.style.WARNING(f"{len(groups)} group(s) without page permission:"))
        for group, group_models in groups.items():
            self.stdout.write(f"- {group.name}")
            self.stdout.write("  Models: " + ", ".join(model._meta.label for model in group_models))
            usernames = sorted(group.user_set.values_list("username", flat=True))
            self.stdout.write("  Members: " + (", ".join(usernames) if usernames else "none"))
