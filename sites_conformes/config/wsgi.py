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

if not settings.DEBUG:
    from dj_static import Cling

    application = Cling(application)
