from django.contrib.auth.forms import SetPasswordForm
from wagtail.admin.forms.auth import PasswordResetForm as WagtailPasswordResetForm

from sites_conformes.forms.baseform import SitesFacilesBaseForm


class DsfrPasswordResetForm(SitesFacilesBaseForm, WagtailPasswordResetForm):
    pass


class DsfrSetPasswordForm(SitesFacilesBaseForm, SetPasswordForm):
    pass
