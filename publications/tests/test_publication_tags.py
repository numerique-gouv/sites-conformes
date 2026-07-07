from django.test import RequestFactory, SimpleTestCase

from publications.templatetags.publication_tags import filters_query, toggle_url_filter


class ToggleUrlFilterTestBase(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _context(self, query_string="", **current):
        path = f"/?{query_string}" if query_string else "/"
        return {"request": self.factory.get(path), **current}


class ToggleUrlFilterPublicationSpecificTest(ToggleUrlFilterTestBase):
    def test_adds_collection_filter(self):
        collection = type("Collection", (), {"slug": "agriculture"})()
        result = toggle_url_filter(self._context(), collection=collection)
        self.assertEqual(result, "?collection=agriculture")

    def test_adds_theme_filter(self):
        theme = type("Theme", (), {"slug": "climate"})()
        result = toggle_url_filter(self._context(), theme=theme)
        self.assertEqual(result, "?theme=climate")

    def test_removes_active_collection_filter(self):
        collection = type("Collection", (), {"slug": "agriculture"})()
        result = toggle_url_filter(
            self._context("collection=agriculture", current_collection=collection),
            collection=collection,
        )
        self.assertEqual(result, "")

    def test_removes_active_collection_while_keeping_theme(self):
        collection = type("Collection", (), {"slug": "agriculture"})()
        result = toggle_url_filter(
            self._context(
                "collection=agriculture&theme=climate",
                current_collection=collection,
            ),
            collection=collection,
        )
        self.assertEqual(result, "?theme=climate")

    def test_uses_filters_dict_with_publication_filters(self):
        collection = type("Collection", (), {"slug": "agriculture"})()
        theme = type("Theme", (), {"slug": "climate"})()
        result = toggle_url_filter(
            self._context("ignored=1"),
            filters_dict={"theme": theme.slug},
            collection=collection,
        )
        self.assertEqual(result, "?theme=climate&collection=agriculture")


class FiltersQueryTest(SimpleTestCase):
    def test_returns_empty_string_when_no_filters(self):
        self.assertEqual(filters_query(None), "")
        self.assertEqual(filters_query({}), "")

    def test_builds_query_string_from_filters_dict(self):
        result = filters_query({"collection": "agriculture", "tag": "news"})
        self.assertEqual(result, "?collection=agriculture&tag=news")
