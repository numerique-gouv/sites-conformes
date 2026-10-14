"""
Strip personal data (e-mail and IP addresses, user identity, session cookies)
from application logs and error e-mails, in the spirit of Sentry's data
scrubbing.

Two complementary layers:

- name-based: request headers, cookies and POST fields whose name looks
  sensitive are replaced by Django's usual "********************" placeholder
  (PIIExceptionReporterFilter);
- pattern-based: e-mail and IP addresses are replaced by "[email]" / "[ip]" in
  the final text, whatever their origin (exception message, local variables,
  log message…) (scrub_pii, used by PIIExceptionReporter and ScrubPIIFilter).

Pattern-based scrubbing is best effort: names or phone numbers embedded in free
text are not detected.
"""

import ipaddress
import logging
import re

from django.views.debug import ExceptionReporter, SafeExceptionReporterFilter

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}")
IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
# Loose candidate, validated with the ipaddress module to avoid false positives
# such as timestamps ("12:30:45").
IPV6_RE = re.compile(r"(?<![\w:])[0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7}(?![\w:])")


def _replace_ip(match: re.Match) -> str:
    try:
        ipaddress.ip_address(match.group())
    except ValueError:
        return match.group()
    return "[ip]"


def scrub_pii(text: str) -> str:
    """Replace e-mail and IP addresses found in text."""
    if not text:
        return text
    text = EMAIL_RE.sub("[email]", text)
    text = IPV4_RE.sub(_replace_ip, text)
    return IPV6_RE.sub(_replace_ip, text)


class PIIExceptionReporterFilter(SafeExceptionReporterFilter):
    """Also hide client IP headers, session cookies and personal POST fields."""

    hidden_settings = re.compile(
        SafeExceptionReporterFilter.hidden_settings.pattern + "|SESSION|REMOTE_ADDR|FORWARDED|REAL_IP|CLIENT_IP",
        flags=re.IGNORECASE,
    )
    hidden_post_parameters = re.compile(r"MAIL|NAME|NOM|PHONE|TELEPHONE|ADDRESS|ADRESSE", flags=re.IGNORECASE)

    def get_post_parameters(self, request):
        cleansed = super().get_post_parameters(request)
        if not self.is_active(request) or not cleansed:
            return cleansed
        cleansed = cleansed.copy()
        for key in cleansed:
            if self.hidden_post_parameters.search(key):
                cleansed[key] = self.cleansed_substitute
        return cleansed


class PIIExceptionReporter(ExceptionReporter):
    """Error report (500 e-mails) without the current user nor e-mail/IP addresses."""

    def get_traceback_data(self):
        data = super().get_traceback_data()
        if data.get("user_str"):
            data["user_str"] = SafeExceptionReporterFilter.cleansed_substitute
        return data

    def get_traceback_text(self):
        return scrub_pii(super().get_traceback_text())

    def get_traceback_html(self):
        return scrub_pii(super().get_traceback_html())


class ScrubPIIFilter(logging.Filter):
    """Logging filter scrubbing the message, traceback and stack of each record."""

    def filter(self, record):
        record.msg = scrub_pii(record.getMessage())
        record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        record.exc_text = scrub_pii(record.exc_text)
        record.stack_info = scrub_pii(record.stack_info)
        return True
