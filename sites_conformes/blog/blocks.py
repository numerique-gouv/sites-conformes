"""Deprecated: these blocks moved to sites_conformes.core.blocks.colophon."""

import warnings

from sites_conformes.core.blocks.colophon import COLOPHON_BLOCKS, ContactCardBlock  # noqa: F401

warnings.warn(
    "sites_conformes.blog.blocks is deprecated and will be removed in the next major version:"
    " import from sites_conformes.core.blocks.colophon instead.",
    DeprecationWarning,
    stacklevel=2,
)
