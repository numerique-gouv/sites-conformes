from django.test import RequestFactory, SimpleTestCase

from publications.templatetags.publication_tags import filters_query, toggle_url_filter


class ToggleUrlFilterTestBase(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _context(self, query_string="", **current):
        path = f"/?{query_string}" if query_string else "/"
        return {"request": self.factory.get(path), **current}


class ToggleUrlFilterBaselineTest(ToggleUrlFilterTestBase):
    def test_returns_empty_string_with_no_params(self):
        result = toggle_url_filter(self._context())
        self.assertEqual(result, "")

    def test_preserves_unrelated_get_params(self):
        result = toggle_url_filter(self._context("page=2"))
        self.assertEqual(result, "?page=2")


class ToggleUrlFilterAddFilterTest(ToggleUrlFilterTestBase):
    def test_adds_tag_filter(self):
        tag = type("Tag", (), {"slug": "news"})()
        result = toggle_url_filter(self._context(), tag=tag)
        self.assertEqual(result, "?tag=news")

    def test_adds_author_filter(self):
        author = type("Author", (), {"id": 7})()
        result = toggle_url_filter(self._context(), author=author)
        self.assertEqual(result, "?author=7")

    def test_adds_year_filter(self):
        result = toggle_url_filter(self._context(), year=2024)
        self.assertEqual(result, "?year=2024")

    def test_adds_filter_while_keeping_existing_params(self):
        author = type("Author", (), {"id": 3})()
        result = toggle_url_filter(self._context("tag=old"), author=author)
        self.assertEqual(result, "?tag=old&author=3")


class ToggleUrlFilterToggleOffTest(ToggleUrlFilterTestBase):
    def test_removes_active_tag_when_it_is_the_only_param(self):
        tag = type("Tag", (), {"slug": "news"})()
        result = toggle_url_filter(
            self._context("tag=news", current_tag=tag),
            tag=tag,
        )
        self.assertEqual(result, "")

    def test_removes_active_tag_while_keeping_other_params(self):
        tag = type("Tag", (), {"slug": "news"})()
        result = toggle_url_filter(
            self._context("tag=news&author=3", current_tag=tag),
            tag=tag,
        )
        self.assertEqual(result, "?author=3")


class ToggleUrlFilterReplaceFilterTest(ToggleUrlFilterTestBase):
    def test_replaces_tag_with_different_value(self):
        current = type("Tag", (), {"slug": "old"})()
        new_tag = type("Tag", (), {"slug": "new"})()
        result = toggle_url_filter(
            self._context("tag=old", current_tag=current),
            tag=new_tag,
        )
        self.assertEqual(result, "?tag=new")


class ToggleUrlFilterFiltersDictTest(ToggleUrlFilterTestBase):
    def test_uses_filters_dict_instead_of_request_get(self):
        tag = type("Tag", (), {"slug": "news"})()
        result = toggle_url_filter(
            self._context("ignored=1"),
            filters_dict={"author": "7"},
            tag=tag,
        )
        self.assertEqual(result, "?author=7&tag=news")

    def test_empty_filters_dict_falls_back_to_request_get(self):
        author = type("Author", (), {"id": 3})()
        result = toggle_url_filter(
            self._context("tag=news"),
            filters_dict={},
            author=author,
        )
        self.assertEqual(result, "?tag=news&author=3")


class ToggleUrlFilterUrlEncodingTest(ToggleUrlFilterTestBase):
    def test_encodes_special_characters_in_get_params(self):
        request = self.factory.get("/", {"tag": "hello world"})
        result = toggle_url_filter({"request": request})
        self.assertEqual(result, "?tag=hello+world")


class FiltersQueryTest(SimpleTestCase):
    def test_returns_empty_string_when_no_filters(self):
        self.assertEqual(filters_query(None), "")
        self.assertEqual(filters_query({}), "")

    def test_builds_query_string_from_filters_dict(self):
        result = filters_query({"collection": "agriculture", "tag": "news"})
        self.assertEqual(result, "?collection=agriculture&tag=news")
