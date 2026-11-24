"""Read settings from the environment and from a ``.env`` file, with django-environ.

django-environ reads ``.env`` values verbatim (it only resolves whole ``$VAR`` values), whereas
python-dotenv (used before) expanded ``${VAR}`` references. Existing ``.env`` files rely on it, e.g.
``DATABASE_URL=postgres://${DATABASE_USER}:...``, so ``read_env`` restores that expansion.

This module only depends on the standard library and django-environ, so ``settings.py`` can import it.
"""

import os
import re
from pathlib import Path

import environ

__all__ = ["env", "read_env"]

# ${NAME} or ${NAME:-default}, like python-dotenv
_VARIABLE_PATTERN = re.compile(r"\$\{(\w+)(?::-([^}]*))?\}")

env = environ.Env()


def read_env(env_file: str | Path) -> None:
    """Load ``env_file`` into ``os.environ``, expanding ``${VAR}`` and ``${VAR:-default}`` references.

    Variables already set in the environment are kept, and their values are never expanded.
    A reference resolves to the environment variable first, then to the ``.env`` value (itself expanded),
    then to its default, then to an empty string. A missing file is ignored.
    """
    file_values: dict[str, str] = {}

    class _FileReader(environ.Env):
        # Collect the parsed values instead of writing them to os.environ
        ENVIRON = file_values

    _FileReader.read_env(env_file)

    for key in file_values:
        os.environ.setdefault(key, _expand(key, file_values, seen=set()))


def _expand(key: str, values: dict[str, str], seen: set[str]) -> str:
    seen = seen | {key}

    def replace(match: re.Match) -> str:
        name, default = match.group(1), match.group(2)
        if name in os.environ:
            return os.environ[name]
        if name in values and name not in seen:
            return _expand(name, values, seen)
        return default or ""

    return _VARIABLE_PATTERN.sub(replace, values[key])
