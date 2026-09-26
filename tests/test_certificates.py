"""Offline lifecycle checks using synthetic keys, never vehicle credentials."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

from leapmotor_cloud.certificates import AccountCertificateManager, CertificateUnavailable


class CertificateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 25, tzinfo=timezone.utc)
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def bundle(self, *, days=10, starts=-1, client=True, ca=False):
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "offline-test")])
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(self.key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(self.now + timedelta(days=starts))
                .not_valid_after(self.now + timedelta(days=days))
                .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
                .add_extension(x509.ExtendedKeyUsage([
                    ExtendedKeyUsageOID.CLIENT_AUTH if client else ExtendedKeyUsageOID.SERVER_AUTH
                ]), critical=False).sign(self.key, hashes.SHA256()))
        return (pkcs12.serialize_key_and_certificates(b"test", self.key, cert, None,
                serialization.BestAvailableEncryption(b"synthetic-password")), b"synthetic-password")

    def manager(self, provider, **kwargs):
        obj = AccountCertificateManager(provider, clock=lambda: self.now, **kwargs)
        self.addCleanup(obj.close)
        return obj

    def test_single_provider_for_concurrent_callers(self):
        material = self.bundle()
        calls = []
        def provider():
            calls.append(1)
            return material
        manager = self.manager(provider)
        with ThreadPoolExecutor(max_workers=8) as pool:
            leases = list(pool.map(lambda _: manager.ensure(), range(16)))
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(x is leases[0] for x in leases))

    def test_renew_keeps_old_paths_until_close(self):
        first = self.bundle(days=2)
        second = self.bundle(days=10)
        values = iter([first, second])
        manager = self.manager(lambda: next(values))
        old = manager.ensure()
        self.now += timedelta(days=1, hours=1)
        new = manager.ensure()
        self.assertNotEqual(old.paths, new.paths)
        self.assertTrue(all(p.exists() for p in old.paths + new.paths))
        for path in old.paths + new.paths:
            if os.name == 'nt':
                from leapmotor_cloud.private_storage import validate_private_directory
                validate_private_directory(path.parent)
                validate_private_directory(path.parent.parent)
            else:
                self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        manager.close()
        self.assertTrue(all(not p.exists() for p in old.paths + new.paths))
        with self.assertRaises(CertificateUnavailable):
            manager.ensure()

    def test_failure_preserves_valid_certificate_and_cooldown(self):
        values = iter([self.bundle(days=2), (b"invalid", b"password")])
        calls = []
        def provider():
            calls.append(1)
            return next(values)
        manager = self.manager(provider)
        old = manager.ensure()
        self.now += timedelta(days=1, hours=1)
        self.assertIs(manager.ensure(), old)
        self.assertTrue(manager.last_refresh_failed)
        self.assertIs(manager.ensure(), old)
        self.assertEqual(len(calls), 2)
        self.now += timedelta(days=2)
        with self.assertRaises(CertificateUnavailable):
            manager.ensure()

    def test_rejects_invalid_material(self):
        for kwargs in ({'days':-0.5}, {'starts':1}, {'client':False}, {'ca':True}, {'days':0.5}):
            with self.subTest(kwargs=kwargs):
                data = self.bundle(**kwargs)
                with self.assertRaises(CertificateUnavailable):
                    self.manager(lambda: data).ensure()

    def test_wrong_password_and_sanitized_error(self):
        data, _ = self.bundle()
        with self.assertRaisesRegex(CertificateUnavailable, '^Account certificate unavailable$'):
            self.manager(lambda: (data, b"wrong-private-secret")).ensure()
        def failed():
            raise RuntimeError("private-token-and-password")
        with self.assertRaisesRegex(CertificateUnavailable, '^Account certificate unavailable$'):
            self.manager(failed).ensure()

    def test_checks_time_after_provider(self):
        data = self.bundle(days=2)
        def slow():
            self.now += timedelta(days=3)
            return data
        with self.assertRaises(CertificateUnavailable):
            self.manager(slow).ensure()


if __name__ == '__main__':
    unittest.main()
