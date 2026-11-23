from dj_static import Cling, MediaCling
from django.test import SimpleTestCase


def _noop_app(environ, start_response):
    return []


class DjStaticSettingsTestCase(SimpleTestCase):
    """config/wsgi.py serves static files with dj_static when DEBUG and WhiteNoise are off.

    dj_static builds file paths with ``root + path_info``, so STATIC_ROOT and MEDIA_ROOT must be strings,
    not ``pathlib.Path`` objects (which made every static file return a 500).
    """

    def test_static_root_is_usable_by_dj_static(self):
        cling = Cling(_noop_app, ignore_debug=True)
        self.assertTrue(cling.cling._full_path("/css/style.css").endswith("staticfiles/css/style.css"))

    def test_media_root_is_usable_by_dj_static(self):
        cling = MediaCling(_noop_app)
        self.assertIsInstance(cling.cling._full_path("/images/photo.jpg"), str)
