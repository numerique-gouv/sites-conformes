from django.http import HttpResponse, HttpResponseNotFound
from django.views import View

from db_storage.models import StoredFile


class ServeFileView(View):
    """
    Serves files stored in the database.
    Sets correct Content-Type and caching headers.
    """

    def get(self, request):
        name = request.GET.get("name")
        if not name:
            return HttpResponseNotFound("File not found.")

        try:
            stored_file = StoredFile.objects.get(name=name)
        except StoredFile.DoesNotExist:
            return HttpResponseNotFound("File not found.")

        response = HttpResponse(
            bytes(stored_file.content),
            content_type=stored_file.content_type,
        )
        response["Content-Length"] = stored_file.size
        response["Cache-Control"] = "public, max-age=3600"
        return response
