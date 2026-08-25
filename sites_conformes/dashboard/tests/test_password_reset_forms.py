"""
Regression tests for the DSFR styling of the Wagtail admin password reset forms.

django-dsfr 3.5.x changed `{% dsfr_form_field %}` / `{{ field.as_field_group }}` to only
produce DSFR markup for forms whose bound_field_class is dsfr.forms.DsfrBoundField (i.e.
forms subclassing dsfr.forms.DsfrBaseForm). Wagtail's built-in password reset forms don't,
so they silently lost their styling. sites_conformes.dashboard.forms.DsfrPasswordResetForm
and DsfrSetPasswordForm fix this; config.settings.WAGTAILADMIN_USER_PASSWORD_RESET_FORM and
the wagtailadmin_password_reset_confirm URL override in config.urls wire them into the
actual views.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, override_settings
from django.urls import resolve, reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from dsfr.forms import DsfrBoundField

from sites_conformes.dashboard.forms import DsfrPasswordResetForm, DsfrSetPasswordForm

User = get_user_model()


class PasswordResetFormsDsfrRenderingTestCase(TestCase):
    """Form-level checks: DSFR markup doesn't depend on going through a view."""

    def test_password_reset_form_email_field_is_dsfr_styled(self):
        form = DsfrPasswordResetForm()

        bound_field = form["email"]
        self.assertIsInstance(bound_field, DsfrBoundField)

        html = str(bound_field.as_field_group())
        self.assertIn("fr-input-group", html)
        self.assertIn('class="fr-input"', html)

    def test_set_password_form_fields_are_dsfr_styled(self):
        user = User(username="jane", email="jane@example.com")
        form = DsfrSetPasswordForm(user=user)

        for field_name in ["new_password1", "new_password2"]:
            bound_field = form[field_name]
            self.assertIsInstance(bound_field, DsfrBoundField)

            html = str(bound_field.as_field_group())
            self.assertIn("fr-input-group", html)
            self.assertIn('class="fr-input"', html)


@override_settings(WAGTAIL_PASSWORD_RESET_ENABLED=True)
class PasswordResetViewsDsfrRenderingTestCase(TestCase):
    """End-to-end checks that the actual admin views render the DSFR-styled forms."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="jane", email="jane@example.com", password="a-strong-password-123"
        )

    def test_password_reset_view_renders_dsfr_markup(self):
        response = self.client.get(reverse("wagtailadmin_password_reset"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "fr-input-group")
        self.assertContains(response, 'class="fr-input"')

    def test_password_reset_confirm_url_is_overridden_with_dsfr_view(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        url = reverse("wagtailadmin_password_reset_confirm", kwargs={"uidb64": uid, "token": token})

        match = resolve(url)
        self.assertIs(match.func.view_class.form_class, DsfrSetPasswordForm)

    def test_password_reset_confirm_view_renders_dsfr_markup(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        url = reverse("wagtailadmin_password_reset_confirm", kwargs={"uidb64": uid, "token": token})

        # Django's PasswordResetConfirmView redirects the token out of the URL and into the
        # session on first GET, so the actual form is only served on the followed response.
        response = self.client.get(url, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "fr-input-group")
        self.assertContains(response, 'class="fr-input"')
