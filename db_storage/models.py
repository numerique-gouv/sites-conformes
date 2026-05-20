import mimetypes

from django.db import models


class StoredFile(models.Model):
    name = models.CharField(
        max_length=512,
        unique=True,
        db_index=True,
        help_text="Full storage path (e.g. 'images/my_photo.jpg')",
    )
    content = models.BinaryField(
        help_text="Raw file bytes",
    )
    content_type = models.CharField(
        max_length=256,
        blank=True,
        default="",
        help_text="MIME type (e.g. 'image/jpeg')",
    )
    size = models.PositiveIntegerField(
        default=0,
        help_text="File size in bytes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "stored file"
        verbose_name_plural = "stored files"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.content_type:
            guessed_type, _ = mimetypes.guess_type(self.name)
            self.content_type = guessed_type or "application/octet-stream"
        if self.content and not self.size:
            self.size = len(self.content)
        super().save(*args, **kwargs)
