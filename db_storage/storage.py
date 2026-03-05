import mimetypes
import os
import posixpath
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.urls import reverse
from django.utils.deconstruct import deconstructible


@deconstructible
class DatabaseStorage(Storage):
    """
    Django storage backend that stores files in PostgreSQL via the StoredFile model.
    """

    def _open(self, name, mode="rb"):
        from db_storage.models import StoredFile

        stored_file = StoredFile.objects.get(name=name)
        f = ContentFile(bytes(stored_file.content))
        f.name = name
        return f

    def _save(self, name, content):
        from db_storage.models import StoredFile

        if hasattr(content, "read"):
            data = content.read()
        else:
            data = content

        if isinstance(data, str):
            data = data.encode("utf-8")

        content_type, _ = mimetypes.guess_type(name)
        content_type = content_type or "application/octet-stream"

        StoredFile.objects.update_or_create(
            name=name,
            defaults={
                "content": data,
                "content_type": content_type,
                "size": len(data),
            },
        )
        return name

    def delete(self, name):
        from db_storage.models import StoredFile

        StoredFile.objects.filter(name=name).delete()

    def exists(self, name):
        from db_storage.models import StoredFile

        return StoredFile.objects.filter(name=name).exists()

    def listdir(self, path):
        from db_storage.models import StoredFile

        path = path.rstrip("/")
        if path:
            path += "/"

        files = []
        dirs = set()

        entries = StoredFile.objects.filter(name__startswith=path).values_list("name", flat=True)
        for entry in entries:
            relative = entry[len(path) :]
            if "/" in relative:
                dirs.add(relative.split("/")[0])
            else:
                files.append(relative)

        return sorted(dirs), sorted(files)

    def size(self, name):
        from db_storage.models import StoredFile

        return StoredFile.objects.get(name=name).size

    def url(self, name):
        return reverse("db_storage:serve_file") + "?name=" + name

    def get_available_name(self, name, max_length=None):
        if not self.exists(name):
            return name

        dir_name, file_name = os.path.split(name)
        file_root, file_ext = os.path.splitext(file_name)

        count = 1
        while self.exists(name):
            name = posixpath.join(dir_name, f"{file_root}_{count}{file_ext}")
            count += 1

        return name
