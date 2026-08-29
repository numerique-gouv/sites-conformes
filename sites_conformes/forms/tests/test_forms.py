import time

from django.core import mail
from django.core.management import call_command
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils.translation import gettext as _
from dsfr.forms import DsfrBoundField
from wagtail.test.utils import WagtailPageTestCase
from wagtail_localize.models import TranslationSource

from sites_conformes.forms.models import FormField, FormPage, SitesFacilesFormBuilder

AUTOMATIC_EMAIL_NOTICE = _(
    "This message was generated automatically following the submission of a form on your website. "
    "Please do not reply directly to this e-mail: your reply would not reach the sender. "
    "To answer the person, use the e-mail address given in the form below."
)


class FormsTestCase(WagtailPageTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        call_command("collectstatic", interactive=False)
        call_command("create_starter_pages")

    def test_form_page_is_renderable(self):
        form_page = FormPage.objects.first()
        self.assertPageIsRenderable(form_page)

    def test_correct_form_is_submitted(self):
        form_page = FormPage.objects.first()
        post_data = {
            "votre_nom_complet": "Félix Faure",
            "votre_adresse_electronique": "no7@elysee.fr",
            "titre_de_votre_message": "Ma connaissance",
            "votre_message": "S’est enfuie par l’escalier !",
        }
        response = self.client.post(form_page.url, post_data)

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "<p>Merci pour votre message ! Nous reviendrons vers vous rapidement.</p>",
        )

    def test_submission_email_starts_with_automatic_notice(self):
        """
        The notification e-mail sent to the site administrator must start with a notice
        explaining the message is automatic and should not be replied to, so that editors
        do not answer the site address instead of the person who submitted the form.
        """
        form_page = FormPage.objects.first()
        form_page.to_address = "admin@example.org"
        form_page.from_address = "no-reply@example.org"
        form_page.subject = "Nouveau message"
        form_page.save()

        post_data = {
            "votre_nom_complet": "Félix Faure",
            "votre_adresse_electronique": "no7@elysee.fr",
            "titre_de_votre_message": "Ma connaissance",
            "votre_message": "S’est enfuie par l’escalier !",
            # Honeypot fields (enabled by default): empty name + a submission time
            # older than the required interval, so the submission is not treated as spam.
            "whf_name": "",
            "whf_time": str(int(time.time()) - 60),
        }
        response = self.client.post(form_page.url, post_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

        body = mail.outbox[0].body
        # The notice comes first, before the form content.
        self.assertTrue(body.startswith(AUTOMATIC_EMAIL_NOTICE))
        # The submitted form content is still present.
        self.assertIn("Votre nom complet: Félix Faure", body)
        self.assertLess(body.index(AUTOMATIC_EMAIL_NOTICE), body.index("Votre nom complet"))

    def test_submission_email_reply_to_is_submitter_address(self):
        """
        The notification e-mail must set Reply-To to the address entered in the form's
        e-mail field, so replying answers the person who submitted the form rather than
        the site's own address.
        """
        form_page = FormPage.objects.first()
        form_page.to_address = "admin@example.org"
        form_page.from_address = "no-reply@example.org"
        form_page.subject = "Nouveau message"
        form_page.save()

        post_data = {
            "votre_nom_complet": "Félix Faure",
            "votre_adresse_electronique": "no7@elysee.fr",
            "titre_de_votre_message": "Ma connaissance",
            "votre_message": "S’est enfuie par l’escalier !",
            "whf_name": "",
            "whf_time": str(int(time.time()) - 60),
        }
        response = self.client.post(form_page.url, post_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

        message = mail.outbox[0]
        self.assertEqual(message.reply_to, ["no7@elysee.fr"])
        self.assertEqual(message.from_email, "no-reply@example.org")

    def test_incorrect_form_is_rejected(self):
        form_page = FormPage.objects.first()
        post_data = {
            "votre_nom_complet": "Félix Faure",
            "votre_adresse_electronique": "bad_email",
            "titre_de_votre_message": "",
            "votre_message": "S’est enfuie par l’escalier !",
        }
        response = self.client.post(form_page.url, post_data)

        self.assertEqual(response.status_code, 200)

        self.assertInHTML(
            """<li class="fr-error-text">Saisissez une adresse e-mail valide.</li>""",
            response.content.decode(),
        )

        self.assertRegex(
            response.content.decode(),
            r"<li class=\"fr-error-text\">(\\n)?\s*(Ce champ est requis|Ce champ est obligatoire)\.(\\n)?\s*<\/li>",
        )
        # Updates sometimes mess with the order of the translations and so the displayed translation. Both are fine.

    def test_form_field_clean_name_set_on_save(self):
        """
        Regression test: FormField.clean_name must never be empty after save.

        Certain code paths (e.g. reconstruction from a page revision via
        from_serializable_data) can produce FormField instances whose pk is
        already set before save() is called, causingAbstractFormField.save()
        to skip the clean_name computation (it only runs when pk is None).
        This leaves clean_name as "" in the database, making all BO responses
        appear as None.
        """
        form_page = FormPage.objects.first()

        # Simulate the problematic path: a FormField whose pk is pre-assigned
        # (non-None) but whose clean_name is still empty, as happens when
        # from_serializable_data reconstructs a child object from a revision.
        field = FormField.objects.filter(page=form_page).first()
        original_clean_name = field.clean_name

        field.clean_name = ""
        field.save()

        field.refresh_from_db()
        self.assertNotEqual(field.clean_name, "", "clean_name should not be empty after save")
        self.assertEqual(field.clean_name, original_clean_name)

    def test_get_data_fields_has_no_empty_clean_names(self):
        """
        Regression test: every FormField returned by get_data_fields() must
        have a non-empty clean_name.

        If clean_name is "" in the DB, get_data_fields() returns ("", label)
        tuples. The BO then calls form_data.get("") which is always None, and
        the xlsx export collapses all "" keys so every column header becomes
        the last field's label.
        """
        form_page = FormPage.objects.first()

        # Force empty clean_names on all fields to simulate the buggy state.
        FormField.objects.filter(page=form_page).update(clean_name="")

        # Re-save each field; the overridden save() must restore clean_name.
        for field in FormField.objects.filter(page=form_page):
            field.save()

        data_fields = form_page.get_data_fields()
        for name, label in data_fields:
            if name == "submit_time":
                continue
            self.assertNotEqual(name, "", f"Field '{label}' has an empty clean_name after save()")

    def test_form_field_labels_are_translatable(self):
        form_page = FormPage.objects.first()
        source, _ = TranslationSource.update_or_create_from_instance(form_page)
        source_strings = {segment.context.path for segment in source.stringsegment_set.select_related("context")}

        label_paths = [path for path in source_strings if path.endswith(".label")]
        self.assertTrue(label_paths, "Form field labels should be extracted as translatable string segments")

    def test_form_page_is_found_in_search_results(self):
        call_command("update_index")

        search_url = reverse("cms_search")
        response = self.client.get(f"{search_url}?q=contact")

        self.assertEqual(response.status_code, 200)
        self.assertInHTML("""<a href="/contact/">Contact</a>""", response.content.decode())
        self.assertInHTML("""<h1>1 résultat pour la recherche «\xa0contact\xa0»</h1>""", response.content.decode())


class SitesFacilesCustomFormDsfrRenderingTestCase(SimpleTestCase):
    """
    Regression test: SitesFacilesCustomForm (used by SitesFacilesFormBuilder for every public
    FormPage) must keep dispatching to DSFR's per-widget snippet templates. It only sets the
    "fr-input"/"fr-select" classes itself (via dsfr_input_class_attr); checkboxes and radio
    buttons get no styling at all unless bound_field_class is DsfrBoundField, since their
    markup (fr-checkbox-group, fr-fieldset/legend, etc.) comes entirely from those snippets.
    """

    def build_form(self, **fields):
        builder = SitesFacilesFormBuilder(list(fields.values()))
        return builder.get_form_class()()

    def test_checkbox_field_has_dsfr_markup(self):
        checkbox = FormField(field_type="checkbox", label="Accepte les conditions", required=True)
        form = self.build_form(checkbox=checkbox)

        bound_field = form["accepte_les_conditions"]
        self.assertIsInstance(bound_field, DsfrBoundField)

        html = str(bound_field.as_field_group())
        self.assertIn("fr-checkbox-group", html)

    def test_radio_field_has_dsfr_markup(self):
        radio = FormField(field_type="radio", label="Choix", required=True, choices="A, B")
        form = self.build_form(radio=radio)

        bound_field = form["choix"]
        self.assertIsInstance(bound_field, DsfrBoundField)

        html = str(bound_field.as_field_group())
        self.assertIn("fr-fieldset", html)
        self.assertIn("fr-radio-group", html)
