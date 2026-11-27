from collections.abc import Iterator
from pathlib import Path

from django.template import Template, TemplateSyntaxError, engines
from django.template.base import NodeList, Variable, VariableNode
from django.template.loader_tags import BlockNode, ExtendsNode
from django.test import SimpleTestCase

import sites_conformes

# Blocks filled by the root templates (iframe.html, standalone.html):
# a child template overriding them must keep the parent content.
BLOCKS_REQUIRING_SUPER = {"extra_css", "extra_js"}

PACKAGE_DIR = Path(sites_conformes.__file__).parent


def get_package_templates() -> list[Path]:
    return sorted(PACKAGE_DIR.glob("**/templates/**/*.html"))


def get_overridden_blocks(path: Path) -> list[BlockNode]:
    """
    Returns the blocks of BLOCKS_REQUIRING_SUPER redefined by a child template
    (root templates, which define these blocks, are ignored).
    """
    engine = engines["django"].engine
    template = Template(path.read_text(encoding="utf-8"), engine=engine)

    if not template.nodelist.get_nodes_by_type(ExtendsNode):
        return []

    return [
        node
        for node in template.nodelist.get_nodes_by_type(BlockNode)
        if isinstance(node, BlockNode) and node.name in BLOCKS_REQUIRING_SUPER
    ]


def iter_own_variable_nodes(nodelist: NodeList) -> Iterator[VariableNode]:
    """
    Yields the VariableNodes of a nodelist, without entering nested blocks
    (their {{ block.super }} refers to another block).
    """
    for node in nodelist:
        if isinstance(node, VariableNode):
            yield node
        elif not isinstance(node, BlockNode):
            for attr in node.child_nodelists:
                child_nodelist = getattr(node, attr, None)
                if child_nodelist:
                    yield from iter_own_variable_nodes(child_nodelist)


def calls_super(block: BlockNode) -> bool:
    return any(
        isinstance(node.filter_expression.var, Variable) and node.filter_expression.var.lookups == ("block", "super")
        for node in iter_own_variable_nodes(block.nodelist)
    )


class CallsSuperTestCase(SimpleTestCase):
    def get_block(self, content: str) -> BlockNode:
        template = Template(f"{{% block extra_css %}}{content}{{% endblock %}}", engine=engines["django"].engine)
        return next(
            node
            for node in template.nodelist.get_nodes_by_type(BlockNode)
            if isinstance(node, BlockNode) and node.name == "extra_css"
        )

    def test_block_super(self):
        self.assertTrue(calls_super(self.get_block("{{ block.super }}")))

    def test_block_super_with_filter(self):
        self.assertTrue(calls_super(self.get_block("{{ block.super|safe }}")))

    def test_super_in_nested_block_only(self):
        self.assertFalse(calls_super(self.get_block("{% block inner %}{{ block.super }}{% endblock %}")))

    def test_super_in_wrapper_tag(self):
        self.assertTrue(calls_super(self.get_block("{% if x %}{{ block.super }}{% endif %}")))


class TemplateBlockSuperTestCase(SimpleTestCase):
    def test_overridden_blocks_call_super(self):
        violations = []
        for path in get_package_templates():
            relative_path = path.relative_to(PACKAGE_DIR)
            try:
                blocks = get_overridden_blocks(path)
            except TemplateSyntaxError as e:
                self.fail(f"{relative_path} could not be parsed: {e}")

            violations += [f"{relative_path}: {block.name}" for block in blocks if not calls_super(block)]

        self.assertEqual(violations, [], "These blocks must include {{ block.super }}")

    def test_scan_finds_known_overrides(self):
        # Guards against the previous test silently checking nothing
        overriding_templates = {
            path.relative_to(PACKAGE_DIR).as_posix() for path in get_package_templates() if get_overridden_blocks(path)
        }
        self.assertIn("forms/templates/sites_conformes_forms/form_page.html", overriding_templates)
        self.assertIn("events/templates/sites_conformes_events/events_index_page.html", overriding_templates)
