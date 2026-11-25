from django.contrib.auth.forms import SetPasswordForm
from wagtail.admin.forms.auth import PasswordResetForm as WagtailPasswordResetForm

from sites_conformes.forms.baseform import SitesConformesBaseForm


class DsfrPasswordResetForm(SitesConformesBaseForm, WagtailPasswordResetForm):
    pass


class DsfrSetPasswordForm(SitesConformesBaseForm, SetPasswordForm):
    pass
