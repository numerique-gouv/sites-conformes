from django import forms
from django.db import models
from django.utils.translation import gettext_lazy as _
from dsfr.forms import DsfrDjangoTemplates
from dsfr.utils import dsfr_input_class_attr
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.api import APIField
from wagtail.contrib.forms.forms import BaseForm, FormBuilder
from wagtail.contrib.forms.models import AbstractEmailForm, AbstractFormField
from wagtail.contrib.forms.panels import FormSubmissionsPanel
from wagtail.fields import RichTextField
from wagtail_honeypot.models import HoneypotFormMixin, HoneypotFormSubmissionMixin

from forms.widgets import CustomEmailInputWidget


class FormField(AbstractFormField):
    CHOICES = (
        ("singleline", _("Text field")),
        ("multiline", _("Text area")),
        ("email", _("Email")),
        ("number", _("Number")),
        ("url", _("URL")),
        ("checkbox", _("Checkbox")),
        ("checkboxes", _("Checkboxes")),
        ("dropdown", _("Drop down")),
        ("radio", _("Radio buttons")),
        ("date", _("Date")),
        # ("datetime", _("Date/time")),
        ("hidden", _("Hidden field")),
    )

    page = ParentalKey("FormPage", on_delete=models.CASCADE, related_name="form_fields")

    field_type = models.CharField(verbose_name=_("Field type"), max_length=16, choices=CHOICES)

    class Meta(AbstractFormField.Meta):
        verbose_name = _("Form field")
        verbose_name_plural = _("Form fields")


class SitesFacilesCustomForm(BaseForm):
    """
    A base form that adds the necessary DSFR class on relevant fields
    """

    template_name = "dsfr/form_snippet.html"  # type: ignore

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for visible in self.visible_fields():
            dsfr_input_class_attr(visible)

        for field in self.errors.keys():
            self.fields[field].widget.attrs.update({"autofocus": ""})
            break

    @property
    def default_renderer(self):
        return DsfrDjangoTemplates


class SitesFacilesFormBuilder(FormBuilder):
    def create_date_field(self, field, options):
        options["widget"] = forms.DateInput(attrs={"type": "date"})
        return forms.DateField(**options)

    # Datetime is currently not managed
    def create_datetime_field(self, field, options):
        options["widget"] = forms.DateInput(attrs={"type": "datetime-local"})
        return forms.DateField(**options)

    def create_email_field(self, field, options):
        options["widget"] = CustomEmailInputWidget
        return super().create_email_field(field, options)

    def get_form_class(self):
        return type("WagtailForm", (SitesFacilesCustomForm,), self.formfields)


class FormPage(HoneypotFormMixin, HoneypotFormSubmissionMixin, AbstractEmailForm):
    intro = RichTextField(blank=True)
    thank_you_text = RichTextField(blank=True)

    content_panels = AbstractEmailForm.content_panels + [
        FormSubmissionsPanel(),
        FieldPanel("intro", heading=_("Introduction")),
        InlinePanel("form_fields", label=_("Form field"), heading=_("Form fields")),
        FieldPanel("thank_you_text", heading=_("Thank you text")),
        MultiFieldPanel(
            [
                FieldRowPanel(
                    [
                        FieldPanel("from_address", classname="col6"),
                        FieldPanel("to_address", classname="col6"),
                    ]
                ),
                FieldPanel("subject"),
            ],
            _("E-mail notification when an answer is sent"),
            help_text=_("Optional, will only work if SMTP parameters have been set."),
        ),
    ]

    honeypot_panels = [
        MultiFieldPanel(
            [FieldPanel("honeypot")],
            heading=_("Reduce Form Spam"),
        )
    ]

    promote_panels = AbstractEmailForm.promote_panels + honeypot_panels

    api_fields = [
        APIField("intro"),
        APIField("thank_you_text"),
        APIField("form_fields"),
    ]

    class Meta:
        verbose_name = _("Form page")
        verbose_name_plural = _("Form pages")

    form_builder = SitesFacilesFormBuilder

    def all_fields_required(self):
        """
        Returns True if all fields in the form are mandatory.
        """
        return all(field.get("required", False) for field in self.form_fields.values())
