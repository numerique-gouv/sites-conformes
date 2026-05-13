from django.utils.translation import gettext_lazy as _
from dsfr.constants import VIDEO_RATIOS
from wagtail import blocks
from wagtail.images import get_image_model
from wagtail.images.blocks import ImageBlock

from sites_conformes.content_manager.constants import (
    MEDIA_WIDTH_CHOICES,
)

Image = get_image_model()


## Image
class ImageBlockWithDefault(ImageBlock):
    def __init__(
        self, *args, default_image_title=None, default_image_decorative=True, default_image_alt_text="", **kwargs
    ):
        self._default_image_title = default_image_title
        self._default_image_alt_text = default_image_alt_text
        self._default_image_decorative = default_image_decorative
        super().__init__(*args, **kwargs)

        if "decorative" in self.child_blocks:
            self.child_blocks["decorative"].field.help_text = _(
                "Check if the image is purely decorative. " "In this case, the alt attribute (alt text) will be empty."
            )
        if "alt_text" in self.child_blocks:
            self.child_blocks["alt_text"].field.help_text = _(
                "Used by screen readers if the image is not marked as decorative."
                "Describe the content or purpose of the image in a short, clear sentence."
            )

    def get_default(self):
        if self._default_image_title:
            image = Image.objects.filter(title=self._default_image_title).first()
            if image:
                return {
                    "image": image,
                    "alt_text": self._default_image_alt_text,
                    "decorative": self._default_image_decorative,
                }
        return super().get_default()


class IframeBlock(blocks.StructBlock):
    title = blocks.CharBlock(
        label=_("Title"),
        help_text=_("Accessibility: The title should describe, in a clear and concise manner, the embedded content."),
    )
    url = blocks.URLBlock(
        label=_("URL of the iframe"),
        help_text=_("Example for Tally: https://tally.so/embed/w2jMRa"),
    )
    height = blocks.IntegerBlock(label=_("Height (in pixels)"))
    parameters = blocks.CharBlock(
        label=_("Parameters"),
        help_text=_("""For example: "allow='geolocation'"."""),
        required=False,
    )

    class Meta:
        icon = "globe"
        template = "sites_conformes_content_manager/blocks/iframe.html"


class TranscriptionBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Title"), default="Transcription", required=False)
    content = blocks.RichTextBlock(label=_("Transcription content"), required=False)

    class Meta:
        icon = "media"
        template = "sites_conformes_content_manager/blocks/transcription.html"


class VideoBlock(blocks.StructBlock):
    title = blocks.CharBlock(label=_("Video title"), required=False)
    caption = blocks.CharBlock(label=_("Caption"), required=False)
    url = blocks.URLBlock(
        label=_("Video URL"),
        help_text=_(
            "Use embed format, with a version that doesn't require a consent banner if available."
            " (e.g. : https://www.youtube-nocookie.com/embed/gLzXOViPX-0)"
            " For Youtube, use Embed video and check Enable privacy-enhanced mode."
        ),
    )

    width = blocks.ChoiceBlock(
        label=_("Witdh"),
        choices=MEDIA_WIDTH_CHOICES,
        required=False,
        default="",
    )
    video_ratio = blocks.ChoiceBlock(
        label=_("Video ratio"),
        choices=VIDEO_RATIOS,
        required=False,
        default="h3",
    )
    transcription = TranscriptionBlock(label=_("Transcription"), required=False)

    class Meta:
        icon = "media"
        template = "sites_conformes_content_manager/blocks/video.html"
