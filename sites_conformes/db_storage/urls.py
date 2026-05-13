from django.urls import path

from sites_conformes.db_storage.views import ServeFileView

app_name = "db_storage"

urlpatterns = [
    path("serve/", ServeFileView.as_view(), name="serve_file"),
]
