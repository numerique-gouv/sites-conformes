from django import forms
from django.db import models
from django.utils.translation import gettext_lazy as _
from dsfr.forms import DsfrBoundField, DsfrDjangoTemplates
from dsfr.utils import dsfr_input_class_attr
from modelcluster.fields import ParentalKey
from wagtail.admin.mail import send_mail
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

from sites_conformes.forms.widgets import CustomEmailInputWidget


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

    def render_email(self, form):
        notice = _(
            "This message was generated automatically following the submission of a form on your website. "
            "Please do not reply directly to this e-mail: your reply would not reach the sender. "
            "To answer the person, use the e-mail address given in the form below."
        )
        return f"{notice}\n\n{super().render_email(form)}"

    def send_mail(self, form):
        """
        Same as Wagtail's AbstractEmailForm.send_mail, but sets Reply-To to the e-mail
        addresses submitted in the form's "email" fields. This way editors replying to
        the notification answer the person who filled the form, not the site address.
        """
        addresses = [x.strip() for x in self.to_address.split(",")]

        email_field_names = [field.clean_name for field in self.form_fields.all() if field.field_type == "email"]
        reply_to = [form.cleaned_data[name] for name in email_field_names if form.cleaned_data.get(name)]

        send_mail(
            self.subject,
            self.render_email(form),
            addresses,
            self.from_address,
            reply_to=reply_to or None,
        )
