from django.utils.translation import gettext_lazy as _
from treebeard.forms import MoveNodeForm
from wagtail.admin.forms import WagtailAdminModelForm


class CategoryForm(MoveNodeForm, WagtailAdminModelForm):
    """Wagtail form for categories, with treebeard's "Relative to" and "Position" fields."""

    def _get_initial(self, instance):
        # Wagtail hands the create view an unsaved instance; treebeard expects a saved one or None.
        return super()._get_initial(instance) if instance.pk else {"treebeard_position": "sorted-child"}

    def _set_ref_model_queryset(self, opts, instance):
        super()._set_ref_model_queryset(opts, instance if instance is not None and instance.pk else None)

    def clean(self):
        cleaned_data = super().clean()
        reference = cleaned_data.get("treebeard_ref_node")
        if reference and self.instance.pk and reference in self.instance.get_descendants(include_self=True):
            self.add_error(
                "treebeard_ref_node", _("A category cannot be moved under itself or one of its sub-categories.")
            )
        return cleaned_data
