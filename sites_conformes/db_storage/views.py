from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound
from django.views import View
from wagtail import hooks
from wagtail.documents import get_document_model

from sites_conformes.db_storage.models import StoredFile


class ServeFileView(View):
    """
    Serves files stored in the database.
    Sets correct Content-Type and caching headers.

    Files that back a Wagtail document go through the same checks as Wagtail's
    own document serve view (``before_serve_document`` hooks, which include the
    collection view restrictions), so that this endpoint cannot be used to
    bypass a login or password restriction.
    """

    def get(self, request):
        name = request.GET.get("name")
        if not name:
            return HttpResponseNotFound("File not found.")

        try:
            stored_file = StoredFile.objects.get(name=name)
        except StoredFile.DoesNotExist:
            return HttpResponseNotFound("File not found.")

        is_restricted = False
        for document in get_document_model().objects.filter(file=name).select_related("collection"):
            for fn in hooks.get_hooks("before_serve_document"):
                result = fn(document, request)
                if isinstance(result, HttpResponse):
                    return result
            if document.collection.get_view_restrictions().exists():
                is_restricted = True

        response = HttpResponse(
            bytes(stored_file.content),
            content_type=stored_file.content_type,
        )
        response["Content-Length"] = stored_file.size
        if is_restricted:
            # Never let a shared cache keep a copy of a restricted document
            response["Cache-Control"] = "private, no-store"
        else:
            response["Cache-Control"] = settings.MEDIA_CACHE_CONTROL
        # Uploaded files (SVG, txt…) are served from the site's origin: prevent script execution and MIME sniffing
        response["Content-Security-Policy"] = "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'"
        response["X-Content-Type-Options"] = "nosniff"
        return response
