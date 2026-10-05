from django import forms
from django.db import models
from django.utils.translation import gettext_lazy as _
from dsfr.forms import DsfrBoundField, DsfrDjangoTemplates
from dsfr.utils import dsfr_input_class_attr
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.api import APIField
from wagtail.contrib.forms.forms import BaseForm, FormBuilder
from wagtail.contrib.forms.models import AbstractEmailForm, AbstractFormField as WagtailAbstractFormField
from wagtail.contrib.forms.panels import FormSubmissionsPanel
from wagtail.contrib.forms.utils import get_field_clean_name
from wagtail.fields import RichTextField
from wagtail.models import TranslatableMixin
from wagtail_honeypot.models import HoneypotFormMixin, HoneypotFormSubmissionMixin
from wagtail_localize.fields import SynchronizedField

from sites_conformes.core import is_model_swapped
from sites_conformes.core.abstract import DefaultTemplateMixin
from sites_conformes.forms.widgets import CustomEmailInputWidget


class AbstractFormField(TranslatableMixin, WagtailAbstractFormField):
    """
    Base class for the fields of a form page. A swapped ``SF_FORMPAGE_MODEL`` declares its own
    concrete subclass, with a ``page`` parental key named ``form_fields`` towards it, as ``FormField`` does below.
    """

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

    field_type = models.CharField(verbose_name=_("Field type"), max_length=16, choices=CHOICES)

    # clean_name is a technical slug derived from the label and used as the HTML field name.
    # It must stay identical across locales so form submissions can be processed correctly.
    override_translatable_fields = [
        SynchronizedField("clean_name", overridable=False),
    ]

    def save(self, *args, **kwargs):
        # Guarantee clean_name is always set, even if pk is already assigned (e.g. when
        # reconstructed from a revision via from_serializable_data before the first DB insert).
        if not self.clean_name:
            self.clean_name = get_field_clean_name(self.label)
        super().save(*args, **kwargs)

    class Meta(TranslatableMixin.Meta, WagtailAbstractFormField.Meta):
        abstract = True
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


class AbstractFormPage(DefaultTemplateMixin, HoneypotFormMixin, HoneypotFormSubmissionMixin, AbstractEmailForm):
    """
    Base class for the swappable form page model (setting ``SF_FORMPAGE_MODEL``).

    Declare the form fields model on the side of the concrete subclass (see ``AbstractFormField``).
    """

    default_template = "sites_conformes_forms/form_page.html"

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
        abstract = True

    form_builder = SitesFacilesFormBuilder

    def get_landing_page_template(self, request, *args, **kwargs):
        # Same fallback as get_template, for the landing page
        return [self.landing_page_template, "sites_conformes_forms/form_page_landing.html"]

    def all_fields_required(self):
        """
        Returns True if all fields in the form are mandatory.
        """
        return all(field.get("required", False) for field in self.form_fields.values())


class FormPage(AbstractFormPage):
    class Meta:
        verbose_name = _("Form page")
        verbose_name_plural = _("Form pages")
        swappable = "SF_FORMPAGE_MODEL"


if not is_model_swapped("SF_FORMPAGE_MODEL"):

    class FormField(AbstractFormField):
        page = ParentalKey("FormPage", on_delete=models.CASCADE, related_name="form_fields")
