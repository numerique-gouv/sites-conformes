"""
Text alignment features for Draftail editor.

Implementation using BlockFeature with custom CSS that preserves content styling.
"""

import wagtail.admin.rich_text.editors.draftail.features as draftail_features
from django.templatetags.static import static
from django.utils.html import format_html
from wagtail import hooks
from wagtail.admin.rich_text.converters.html_to_contentstate import (
    BlockElementHandler,
)


@hooks.register("register_rich_text_features")
def register_text_alignment_features(features):
    """
    Register text alignment block features for Draftail editor.

    Note: Due to Draft.js limitations, alignment is implemented as a wrapper
    block type. The HTML output will be <div class="cmsfr-text-{align}">content</div>
    which allows the content inside to maintain its own styling (H2, bold, etc.)
    via CSS inheritance.
    """

    # Text align left
    features.register_editor_plugin(
        "draftail",
        "text-left",
        draftail_features.BlockFeature(
            {
                "type": "text-left",
                "description": "Aligner à gauche",
                "element": "div",
                "icon": [
                    "M50 200 Q50 140, 110 140 L814 140 Q874 140, 874 200 "
                    "Q874 260, 814 260 L110 260 Q50 260, 50 200 Z "
                    "M50 512 Q50 452, 110 452 L714 452 Q774 452, 774 512 "
                    "Q774 572, 714 572 L110 572 Q50 572, 50 512 Z "
                    "M50 824 Q50 764, 110 764 L814 764 Q874 764, 874 824 "
                    "Q874 884, 814 884 L110 884 Q50 884, 50 824 Z"
                ],
            },
            css={"all": ["content_manager/css/text-alignment.css"]},
        ),
    )

    features.register_converter_rule(
        "contentstate",
        "text-left",
        {
            "from_database_format": {'div[class="cmsfr-text-left"]': BlockElementHandler("text-left")},
            "to_database_format": {
                "block_map": {"text-left": {"element": "div", "props": {"class": "cmsfr-text-left"}}}
            },
        },
    )

    # Text align center
    features.register_editor_plugin(
        "draftail",
        "text-center",
        draftail_features.BlockFeature(
            {
                "type": "text-center",
                "description": "Centrer",
                "element": "div",
                "icon": [
                    "M150 200 Q150 140, 210 140 L814 140 Q874 140, 874 200 "
                    "Q874 260, 814 260 L210 260 Q150 260, 150 200 Z "
                    "M50 512 Q50 452, 110 452 L914 452 Q974 452, 974 512 "
                    "Q974 572, 914 572 L110 572 Q50 572, 50 512 Z "
                    "M150 824 Q150 764, 210 764 L814 764 Q874 764, 874 824 "
                    "Q874 884, 814 884 L210 884 Q150 884, 150 824 Z"
                ],
            },
            css={"all": ["content_manager/css/text-alignment.css"]},
        ),
    )

    features.register_converter_rule(
        "contentstate",
        "text-center",
        {
            "from_database_format": {'div[class="cmsfr-text-center"]': BlockElementHandler("text-center")},
            "to_database_format": {
                "block_map": {"text-center": {"element": "div", "props": {"class": "cmsfr-text-center"}}}
            },
        },
    )

    # Text align right
    features.register_editor_plugin(
        "draftail",
        "text-right",
        draftail_features.BlockFeature(
            {
                "type": "text-right",
                "description": "Aligner à droite",
                "element": "div",
                "icon": [
                    "M150 200 Q150 140, 210 140 L914 140 Q974 140, 974 200 "
                    "Q974 260, 914 260 L210 260 Q150 260, 150 200 Z "
                    "M250 512 Q250 452, 310 452 L914 452 Q974 452, 974 512 "
                    "Q974 572, 914 572 L310 572 Q250 572, 250 512 Z "
                    "M150 824 Q150 764, 210 764 L914 764 Q974 764, 974 824 "
                    "Q974 884, 914 884 L210 884 Q150 884, 150 824 Z"
                ],
            },
            css={"all": ["content_manager/css/text-alignment.css"]},
        ),
    )

    features.register_converter_rule(
        "contentstate",
        "text-right",
        {
            "from_database_format": {'div[class="cmsfr-text-right"]': BlockElementHandler("text-right")},
            "to_database_format": {
                "block_map": {"text-right": {"element": "div", "props": {"class": "cmsfr-text-right"}}}
            },
        },
    )

    # Add to default features
    features.default_features.extend(["text-left", "text-center", "text-right"])


@hooks.register("insert_editor_js")
def editor_js():
    """Inject JavaScript to enhance alignment display in editor."""
    return format_html(
        '<script src="{}"></script>',
        static("content_manager/js/text-alignment.js"),
    )
