import logging
import sys

from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, override_settings

from sites_conformes.core.services.log_scrubbing import (
    PIIExceptionReporter,
    PIIExceptionReporterFilter,
    ScrubPIIFilter,
    scrub_pii,
)

SUBSTITUTE = PIIExceptionReporterFilter.cleansed_substitute
INTEGRITY_ERROR = (
    "duplicate key value violates unique constraint\nDETAIL:  Key (email)=(jane.doe@example.gouv.fr) already exists."
)


class ScrubPIITest(SimpleTestCase):
    def test_email(self):
        self.assertEqual(scrub_pii("Key (email)=(jane.doe+cms@example.gouv.fr)"), "Key (email)=([email])")

    def test_ipv4(self):
        self.assertEqual(scrub_pii("from 192.168.1.42, 10.0.0.1"), "from [ip], [ip]")

    def test_ipv6(self):
        self.assertEqual(scrub_pii("from 2001:db8::1 and ::1"), "from [ip] and [ip]")

    def test_keeps_non_addresses(self):
        text = "at 12:30:45, version 999.1.2.3, file views.py line 42"
        self.assertEqual(scrub_pii(text), text)

    def test_empty(self):
        self.assertIsNone(scrub_pii(None))
        self.assertEqual(scrub_pii(""), "")


class ScrubPIIFilterTest(SimpleTestCase):
    def make_record(self, msg, args=(), exc_info=None):
        return logging.LogRecord("test", logging.ERROR, __file__, 1, msg, args, exc_info)

    def test_message_and_args(self):
        record = self.make_record("Login failed for %s from %s", ("jane@example.fr", "203.0.113.7"))
        self.assertTrue(ScrubPIIFilter().filter(record))
        self.assertEqual(record.getMessage(), "Login failed for [email] from [ip]")

    def test_traceback(self):
        try:
            raise ValueError(INTEGRITY_ERROR)
        except ValueError:
            record = self.make_record("Internal Server Error: /contact/", exc_info=sys.exc_info())

        ScrubPIIFilter().filter(record)
        output = logging.Formatter().format(record)

        self.assertIn("Key (email)=([email])", output)
        self.assertNotIn("jane.doe@example.gouv.fr", output)

    def test_idempotent(self):
        record = self.make_record("jane@example.fr")
        ScrubPIIFilter().filter(record)
        ScrubPIIFilter().filter(record)
        self.assertEqual(record.getMessage(), "[email]")


@override_settings(
    DEBUG=False,
    DEFAULT_EXCEPTION_REPORTER_FILTER=f"{PIIExceptionReporterFilter.__module__}.PIIExceptionReporterFilter",
)
class PIIExceptionReporterTest(SimpleTestCase):
    def get_report(self):
        request = RequestFactory().post(
            "/contact/",
            {"email": "jane.doe@example.gouv.fr", "last_name": "Doe", "message": "Bonjour"},
            REMOTE_ADDR="203.0.113.7",
            HTTP_X_FORWARDED_FOR="198.51.100.23",
        )
        request.COOKIES["sessionid"] = "abcdef123456"
        request.user = User(username="jdoe", email="jane.doe@example.gouv.fr")
        try:
            raise ValueError(INTEGRITY_ERROR)
        except ValueError:
            return PIIExceptionReporter(request, *sys.exc_info(), is_email=True).get_traceback_text()

    def test_report_has_no_personal_data(self):
        report = self.get_report()

        for value in ("jane.doe@example.gouv.fr", "203.0.113.7", "198.51.100.23", "abcdef123456", "jdoe", "Doe"):
            with self.subTest(value=value):
                self.assertNotIn(value, report)

    def test_report_keeps_debugging_information(self):
        report = self.get_report()

        self.assertIn("ValueError", report)
        self.assertIn("Key (email)=([email])", report)
        self.assertIn("/contact/", report)
        self.assertIn("Bonjour", report)
        self.assertIn(f"USER: {SUBSTITUTE}", report)
