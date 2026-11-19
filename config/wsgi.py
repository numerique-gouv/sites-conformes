"""
WSGI config for content_manager project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.conf import settings
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

# When WhiteNoise is enabled, it serves static files itself: wrapping the app with Cling
# would intercept /static/ requests before they reach WhiteNoiseMiddleware.
if not settings.DEBUG and not settings.SF_USE_WHITENOISE:
    from dj_static import Cling

    application = Cling(application)
