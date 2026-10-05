"""A transport failure says why, in one word from a fixed vocabulary.

An install whose Home Assistant could not resolve the cloud's name wrote 9,049 lines of
"Cloud transport failed" over two weeks (leapmotor-mate #381, #384): the cause — DNS — was
visible only in the old library's wording. The transport now names the failure it saw, from a fixed
list, with no host, address or free text from the system: `dns_failure`, `timeout`,
`connection_refused`, `connection_reset`, `network_unreachable`, `certificate_rejected`,
`tls_failure`, `http_protocol`, `invalid_response`, and the two it already named, `redirect_refused`
and `response_too_large`. A sign-in that failed in transport carries the same word.
"""
import errno
import socket
import ssl
import unittest
from datetime import datetime, timezone
import urllib.error
from http.client import HTTPException
from pathlib import Path
from unittest.mock import patch

from leapmotor_cloud.authentication import LoginClient, LoginUnavailable
from leapmotor_cloud.transport import REASONS, Request, TransportError, UrllibTransport

CERTS = (Path("synthetic-cert.pem"), Path("synthetic-key.pem"))


def _transport():
    return UrllibTransport(Path("synthetic-ca.pem"), frozenset({"appgateway.leapmotor-international.de"}))


def _request():
    return Request("GET", "https://appgateway.leapmotor-international.de/x", {})


class TransportFailuresAreNamed(unittest.TestCase):
    CASES = (
        (socket.gaierror(8, "nodename nor servname provided"), "dns_failure"),
        (urllib.error.URLError(socket.gaierror(-3, "Temporary failure in name resolution")), "dns_failure"),
        (TimeoutError("timed out"), "timeout"),
        (urllib.error.URLError(TimeoutError()), "timeout"),
        (ConnectionRefusedError(61, "Connection refused"), "connection_refused"),
        (ConnectionResetError(54, "Connection reset by peer"), "connection_reset"),
        (OSError(errno.ENETUNREACH, "Network is unreachable"), "network_unreachable"),
        (ssl.SSLCertVerificationError(1, "certificate verify failed"), "certificate_rejected"),
        (ssl.SSLError(1, "handshake failure"), "tls_failure"),
        (urllib.error.URLError(ssl.SSLError(1, "wrong version number")), "tls_failure"),
        (HTTPException("bad status line"), "http_protocol"),
        (ValueError("x"), "invalid_response"),
        (OSError("something else"), "transport_failure"),
    )

    def test_each_failure_carries_its_word_and_nothing_else(self):
        for raised, reason in self.CASES:
            with self.subTest(reason=reason):
                with patch("leapmotor_cloud.transport.tls_context", side_effect=raised):
                    with self.assertRaises(TransportError) as caught:
                        _transport().send(_request(), client_cert=CERTS)
                self.assertEqual(caught.exception.reason, reason)
                self.assertEqual(str(caught.exception), "Cloud transport failed: " + reason)
                self.assertNotIn("leapmotor", str(caught.exception))
                self.assertIn(reason, REASONS)

    def test_a_reason_outside_the_vocabulary_is_not_passed_on(self):
        self.assertEqual(TransportError("anything the system said").reason, "transport_failure")
        self.assertEqual(TransportError().reason, "transport_failure")


class ASignInThatFailedInTransportSaysWhy(unittest.TestCase):
    def test_the_login_carries_the_transports_word(self):
        class Failing:
            def send(self, request, *, client_cert):
                raise TransportError("dns_failure")
        client = LoginClient(Failing(), application_cert=CERTS, account_certificate_provider=lambda d: CERTS,
                             clock=lambda: datetime.now(timezone.utc), nonce_factory=lambda: "1")
        with patch("leapmotor_cloud.authentication.certificate_usable", return_value=True):
            with self.assertRaises(LoginUnavailable) as caught:
                client.login("synthetic-user", "synthetic-password", device_id="synthetic-device")
        self.assertEqual(caught.exception.stage, "transport")
        self.assertEqual(caught.exception.reason, "dns_failure")

    def test_a_failure_past_the_transport_carries_no_word(self):
        self.assertIsNone(LoginUnavailable("response").reason)
        self.assertIsNone(LoginUnavailable("transport", reason="not a word").reason)
