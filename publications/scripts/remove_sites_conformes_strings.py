#!/usr/bin/env python3
"""
Remove from publications/django.po any msgid already translated in sites_conformes.

Shared strings stay in Sites Conformes catalogs; publications falls back at runtime.
Run after makemessages, before compilemessages (see: just messages).
"""

from __future__ import annotations

from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parent.parent.parent
PUBLICATIONS_PO = ROOT / "publications/locale/fr/LC_MESSAGES/django.po"
SITES_CONFORMES = ROOT / "sites_conformes"

HEADER = """# Publications-only translations (French).
# Strings shared with Sites Conformes (Filters, Tags, Name, …) are intentionally
# omitted here; Django falls back to sites_conformes.* locale catalogs.
# This file is pruned automatically by publications/scripts/remove_sites_conformes_strings.py (just messages).
#
"""


def sites_conformes_msgids() -> set[str]:
    msgids: set[str] = set()
    for po_path in SITES_CONFORMES.glob("**/locale/fr/LC_MESSAGES/django.po"):
        catalog = polib.pofile(str(po_path))
        msgids.update(entry.msgid for entry in catalog if entry.msgid)
    return msgids


def main() -> None:
    if not PUBLICATIONS_PO.exists():
        raise SystemExit(f"Missing {PUBLICATIONS_PO}")

    shared = sites_conformes_msgids()
    catalog = polib.pofile(str(PUBLICATIONS_PO))
    removed: list[str] = []

    for entry in list(catalog):
        if entry.msgid and entry.msgid in shared:
            catalog.remove(entry)
            removed.append(entry.msgid)

    catalog.save(str(PUBLICATIONS_PO))

    # polib drops our free-form header; restore the convention comment.
    text = PUBLICATIONS_PO.read_text(encoding="utf-8")
    if not text.startswith("# Publications-only"):
        PUBLICATIONS_PO.write_text(HEADER + text.lstrip(), encoding="utf-8")

    if removed:
        print(f"Removed {len(removed)} shared msgid(s) from {PUBLICATIONS_PO.relative_to(ROOT)}:")
        for msgid in sorted(removed):
            print(f"  - {msgid!r}")
    else:
        print(f"No shared msgids to remove in {PUBLICATIONS_PO.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
