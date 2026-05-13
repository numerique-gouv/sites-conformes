"""Authentication URLs ProConnect"""

from django.urls import path
from mozilla_django_oidc.urls import urlpatterns as mozilla_oidc_urls

from sites_conformes.proconnect.views import OIDCLogoutCallbackView, OIDCLogoutView

urlpatterns = [
    # Override the default 'logout/' path from Mozilla Django OIDC with our custom view.
    path("logout/", OIDCLogoutView.as_view(), name="oidc_logout_custom"),
    # Override the Wagtail admin logout view
    path("logout/", OIDCLogoutView.as_view(), name="wagtailadmin_logout"),
    path(
        "logout-callback/",
        OIDCLogoutCallbackView.as_view(),
        name="oidc_logout_callback",
    ),
    *mozilla_oidc_urls,
]
