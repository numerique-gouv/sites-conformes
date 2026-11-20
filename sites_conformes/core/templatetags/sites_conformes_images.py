from django import template
from wagtail.images.templatetags.wagtailimages_tags import PictureNode, image

register = template.Library()


class DynamicSpecPictureNode(PictureNode):
    """
    {% picture %} whose `spec=` variable is resolved at render time and prepended to the literal specs.
    """

    def __init__(self, image_expr, filter_specs, spec_expr, output_var_name=None, attrs=None):
        super().__init__(image_expr, filter_specs, output_var_name=output_var_name, attrs=attrs)
        self.spec_expr = spec_expr

    def render(self, context):
        specs = [spec for spec in [self.spec_expr.resolve(context), *self.filter_specs] if spec]
        # ponytail: a fresh node per render, so the shared node is never mutated and Wagtail's render is reused as is
        return PictureNode(self.image_expr, specs, output_var_name=self.output_var_name, attrs=self.attrs).render(
            context
        )


@register.tag
def picture(parser, token):
    """
    Wagtail's {% picture %}, plus `spec=<variable>` for a filter spec computed outside the template, e.g.
    {% picture value.image spec=value.image_filter_spec format-webp preserve-svg %}
    """
    node = image(parser, token)
    if "spec" not in node.attrs:
        return node
    attrs = {name: value for name, value in node.attrs.items() if name != "spec"}
    return DynamicSpecPictureNode(node.image_expr, node.filter_specs, node.attrs["spec"], node.output_var_name, attrs)
