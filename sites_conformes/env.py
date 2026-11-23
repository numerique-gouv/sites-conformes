"""Read settings from the environment and from a ``.env`` file, with python-decouple.

python-decouple reads ``.env`` values verbatim, whereas python-dotenv (used before) expanded
``${VAR}`` references. Existing ``.env`` files rely on it, e.g.
``DATABASE_URL=postgres://${DATABASE_USER}:...``, so this module restores that expansion.

This module only depends on the standard library and decouple, so ``settings.py`` can import it.
"""

import os
import re
from collections import OrderedDict

from decouple import AutoConfig as BaseAutoConfig, Csv, RepositoryEnv, RepositoryIni

__all__ = ["AutoConfig", "Csv", "ExpandingRepositoryEnv", "config"]

# ${NAME} or ${NAME:-default}, like python-dotenv
_VARIABLE_PATTERN = re.compile(r"\$\{(\w+)(?::-([^}]*))?\}")


class ExpandingRepositoryEnv(RepositoryEnv):
    """``.env`` repository that expands ``${VAR}`` and ``${VAR:-default}`` references.

    A reference resolves to the environment variable first, then to the ``.env`` value (itself expanded),
    then to its default, then to an empty string. Values coming from the environment are never expanded.
    """

    def __getitem__(self, key):
        return self._expand(key, seen=set())

    def _expand(self, key, seen):
        seen = seen | {key}

        def replace(match):
            name, default = match.group(1), match.group(2)
            if name in os.environ:
                return os.environ[name]
            if name in self.data and name not in seen:
                return self._expand(name, seen)
            return default or ""

        return _VARIABLE_PATTERN.sub(replace, self.data[key])


class AutoConfig(BaseAutoConfig):
    """``decouple.AutoConfig`` reading ``.env`` files with ``ExpandingRepositoryEnv``."""

    SUPPORTED = OrderedDict(
        [
            ("settings.ini", RepositoryIni),
            (".env", ExpandingRepositoryEnv),
        ]
    )


# Like decouple.config: looks for the .env file from the caller's directory upwards
config = AutoConfig()
