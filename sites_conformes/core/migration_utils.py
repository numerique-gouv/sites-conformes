"""Helpers shared by data migrations of several apps."""


def rename_revision_field(app_label: str, model_name: str, old_name: str, new_name: str):
    """
    RunPython callables (forward, backward) renaming a field in the stored revisions of a model,
    alongside a RenameField: modelcluster drops the unknown keys when it loads a revision,
    so the drafts would otherwise lose that field.
    """

    def rename(source: str, target: str):
        def run(apps, schema_editor):
            ContentType = apps.get_model("contenttypes", "ContentType")
            Revision = apps.get_model("wagtailcore", "Revision")
            content_type = ContentType.objects.filter(app_label=app_label, model=model_name.lower()).first()
            if content_type is None:
                return
            for revision in Revision.objects.filter(content_type=content_type, content__has_key=source):
                revision.content[target] = revision.content.pop(source)
                revision.save(update_fields=["content"])

        return run

    return rename(old_name, new_name), rename(new_name, old_name)
