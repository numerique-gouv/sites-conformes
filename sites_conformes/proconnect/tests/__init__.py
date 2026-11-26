from unittest import skipUnless

from django.apps import apps

# Skips tests that need the ProConnect app (its models, URLs or signal
# receivers), which is only installed when PROCONNECT_ACTIVATED=True.
# Modules using it must not import ProConnect models at module level.
requires_proconnect = skipUnless(apps.is_installed("sites_conformes.proconnect"), "ProConnect is not activated")
