from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from dsfr.forms import DsfrBoundField, DsfrDjangoTemplates
from dsfr.utils import dsfr_input_class_attr
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.api import APIField
from wagtail.contrib.forms.forms import BaseForm, FormBuilder
from wagtail.contrib.forms.models import AbstractEmailForm, AbstractFormField
from wagtail.contrib.forms.panels import FormSubmissionsPanel
from wagtail.contrib.forms.utils import get_field_clean_name
from wagtail.fields import RichTextField
from wagtail.models import TranslatableMixin
from wagtail_honeypot.models import HoneypotFormMixin, HoneypotFormSubmissionMixin
from wagtail_localize.fields import SynchronizedField

from sites_conformes.forms.autocomplete import (
    AUTOCOMPLETE_CHOICES,
    MANDATORY_AUTOCOMPLETE,
    is_autocomplete_compatible,
)
from sites_conformes.forms.widgets import AutocompleteSelect, CustomEmailInputWidget


class FormField(TranslatableMixin, AbstractFormField):
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
    # field_type must be populated for previews to build the form field (as in AbstractFormField).
    field_type.required_on_save = True

    autocomplete = models.CharField(
        verbose_name=_("Autocomplete"),
        max_length=32,
        blank=True,
        choices=AUTOCOMPLETE_CHOICES,
        help_text=_(
            "Purpose of the field, allowing browsers to fill it automatically. "
            "Only the values relevant to the field type are available."
        ),
    )

    panels = [
        FieldPanel("label"),
        FieldPanel("help_text"),
        FieldPanel("required"),
        FieldPanel("field_type", classname="formbuilder-type"),
        FieldPanel("autocomplete", widget=AutocompleteSelect, classname="formbuilder-autocomplete"),
        FieldPanel("choices", classname="formbuilder-choices"),
        FieldPanel("default_value", classname="formbuilder-default"),
    ]

    api_fields = AbstractFormField.api_fields + [APIField("autocomplete")]

    # clean_name is a technical slug derived from the label and used as the HTML field name.
    # It must stay identical across locales so form submissions can be processed correctly.
    override_translatable_fields = [
        SynchronizedField("clean_name", overridable=False),
        SynchronizedField("autocomplete", overridable=False),
    ]

    def clean(self):
        super().clean()
        if not self.autocomplete and self.field_type in MANDATORY_AUTOCOMPLETE:
            self.autocomplete = MANDATORY_AUTOCOMPLETE[self.field_type]
        if self.autocomplete and not is_autocomplete_compatible(self.autocomplete, self.field_type):
            raise ValidationError(
                {"autocomplete": _("This autocomplete value is not compatible with the selected field type.")}
            )

    def save(self, *args, **kwargs):
        # Guarantee clean_name is always set, even if pk is already assigned (e.g. when
        # reconstructed from a revision via from_serializable_data before the first DB insert).
        if not self.clean_name:
            self.clean_name = get_field_clean_name(self.label)
        super().save(*args, **kwargs)

    class Meta(TranslatableMixin.Meta, AbstractFormField.Meta):
        verbose_name = _("Form field")
        verbose_name_plural = _("Form fields")


class SitesFacilesCustomForm(BaseForm):
    """
    A base form that adds the necessary DSFR class on relevant fields
    """

    template_name = "dsfr/form_snippet.html"  # type: ignore
    bound_field_class = DsfrBoundField

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
    def __init__(self, fields):
        # Ignore fields without a type (e.g. being added in the editor) instead of crashing previews
        super().__init__([field for field in fields if field.field_type])

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

    @property
    def formfields(self):
        formfields = super().formfields
        for field in self.fields:
            autocomplete = getattr(field, "autocomplete", "")
            if autocomplete:
                clean_name = field.clean_name or field.get_field_clean_name()
                formfields[clean_name].widget.attrs["autocomplete"] = autocomplete
        return formfields

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
