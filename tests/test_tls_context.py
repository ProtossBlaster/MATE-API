"""The verification context Leapmotor's own certificates can actually pass.

Python 3.13 turns `VERIFY_X509_STRICT` on by default in `ssl.create_default_context()`. Leapmotor's
server certificate for `appgateway.leapmotor-international.de` carries `basicConstraints CA:FALSE`
together with `keyCertSign` in its key usage, and strict verification refuses exactly that
combination. The same contradiction is in the application certificate the client presents, so it is
a template error across their PKI rather than one bad certificate — and nothing on this side can
reissue either.

Measured 28/09/2026 against the live endpoint, same OpenSSL 3.6.3, only the interpreter differing:

    Python 3.12.13   strict off by default   handshake OK (TLSv1.3)
    Python 3.14.7    strict on by default    SSLCertVerificationError:
                                             Key usage keyCertSign invalid for non-CA cert

So the flag is cleared explicitly. That is narrow: this context trusts ONE pinned certificate — the
Leapmotor app sub-CA handed to the transport — and the transport only speaks to an allowlisted set
of hosts, so the strict checks were adding little on top of a pinned anchor.

🔴 The test forces the flag ON before building, because on Python 3.12 it is off anyway and a test
that merely observes "strict is not set" would pass just as well with the fix reverted.
"""
import ssl
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from leapmotor_cloud.transport import tls_context


class TlsContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ca = Path(self.tmp.name) / "ca.pem"
        self.ca.write_text(ssl.get_default_verify_paths().cafile
                           and Path(ssl.get_default_verify_paths().cafile).read_text() or "")
        if not self.ca.read_text().strip():
            self.skipTest("no system CA bundle to build a context from")

    def tearDown(self):
        self.tmp.cleanup()

    def _strict_default(self):
        """A context exactly like Python 3.13+ hands out: strict verification already on."""
        real = ssl.create_default_context

        def factory(*args, **kwargs):
            context = real(*args, **kwargs)
            context.verify_flags |= ssl.VERIFY_X509_STRICT
            return context

        return mock.patch("ssl.create_default_context", factory)

    def test_strict_verification_is_cleared_even_when_the_interpreter_defaults_it_on(self):
        with self._strict_default():
            context = tls_context(self.ca)
        self.assertFalse(context.verify_flags & ssl.VERIFY_X509_STRICT,
                         "Leapmotor's certificates cannot pass strict verification")

    def test_the_rest_of_the_verification_is_untouched(self):
        with self._strict_default():
            context = tls_context(self.ca)
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN,
                        "a pinned sub-CA must still be allowed to be the anchor")


if __name__ == "__main__":
    unittest.main()
