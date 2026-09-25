import base64
import hashlib
import unittest

from leapmotor_cloud import ValidationError, derive_v2_key, sign_authenticated, sign_login


class SigningTests(unittest.TestCase):
    def setUp(self):
        self.headers = dict(source="leapmotor", channel="1", acceptLanguage="en-US",
                            version="V1.16.4-1", deviceType="android", nonce="12345.0",
                            timestamp="1790332862000", deviceId="synthetic-device")
        self.params = dict(vin="SYNTHETICVIN000001", startTime="1789855200",
                           endTime="1789941599", pageNum="1", pageSize="20")
        self.token = "e30.e30." + base64.urlsafe_b64encode(bytes(range(32))).decode().rstrip("=")
        self.r2 = base64.b64encode(bytes(range(32, 64))).decode()
        self.r3 = base64.b64encode(bytes(range(64, 96))).decode()

    def test_app_body_vector(self):
        self.assertEqual(sign_authenticated(bytes(range(32)), self.headers, self.params),
                         "f1fdfa6c819dfd47a39e5800e65ca138c62802b810ade59660a53e04e89e6feb")

    def test_app_headers_only_vector(self):
        self.assertEqual(sign_authenticated(bytes(range(32)), self.headers, {}),
                         "0a7e160ea418cb2542b354dbca8080e1106f50975695f4e3815d3c39c93709a5")

    def test_order_independent_and_inputs_unchanged(self):
        before = dict(self.headers), dict(self.params)
        self.assertEqual(sign_authenticated(b"key", self.headers, self.params),
                         sign_authenticated(b"key", dict(reversed(list(self.headers.items()))),
                                            dict(reversed(list(self.params.items())))))
        self.assertEqual(before, (self.headers, self.params))

    def test_login_uppercase_sha256(self):
        # Fixed field order independently transcribed from the synthetic input.
        material = "en-US1synthetic-deviceandroid12345.0leapmotor1790332862000V1.16.4-1"
        self.assertEqual(sign_login(self.headers, {}), hashlib.sha256(material.encode()).hexdigest().upper())

    def test_app_key_vector(self):
        self.assertEqual(derive_v2_key(self.token, self.r2, self.r3), bytes(range(96, 128)))

    def test_padded_jwt_signature(self):
        padded = self.token + "=" * (-len(self.token.split(".")[2]) % 4)
        self.assertEqual(derive_v2_key(padded, self.r2, self.r3), bytes(range(96, 128)))

    def test_xor_uses_shortest_length(self):
        self.assertEqual(derive_v2_key(self.token, base64.b64encode(bytes(range(32, 36))).decode(), self.r3),
                         bytes(range(96, 100)))

    def test_bad_token_shapes_are_private_errors(self):
        for bad in (None, "", "private-secret", "a.b", "a.b.c.d", ".e30.YQ", "e30.e30.",
                    "e30.e30.!!!!", "e30.e30.a", "e30.e30.YR", "e30.e30.YQ==="):
            with self.subTest(token_type=type(bad).__name__):
                with self.assertRaises(ValidationError) as error:
                    derive_v2_key(bad, self.r2, self.r3)
                self.assertEqual(str(error.exception), "Invalid signing material")

    def test_invalid_or_empty_base64_material(self):
        for bad in (None, "", "private secret", "YQ", "YQ==\n", "YQ====", "!!!!", "YR=="):
            with self.subTest(material_type=type(bad).__name__):
                with self.assertRaises(ValidationError):
                    derive_v2_key(self.token, bad, self.r3)
                with self.assertRaises(ValidationError):
                    derive_v2_key(self.token, self.r2, bad)

    def test_invalid_keys(self):
        for key in (b"", None, "private-secret", bytearray(b"key")):
            with self.assertRaises(ValidationError):
                sign_authenticated(key, self.headers, {})

    def test_non_string_signing_values(self):
        for value in (None, True, 1, 1.0, [], {}):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ValidationError):
                    sign_authenticated(b"key", self.headers, {"pageNum": value})

    def test_missing_extra_empty_and_colliding_base_fields(self):
        for headers, params in (({}, {}), (dict(self.headers, extra="x"), {}),
                                (dict(self.headers, version=""), {}),
                                (self.headers, {"nonce": "collision"})):
            with self.assertRaises(ValidationError):
                sign_authenticated(b"key", headers, params)

    def test_invalid_mappings_names_and_encoding(self):
        for params in (None, [], {"": "value"}, {1: "value"}, {"a-b": "value"},
                       {"value": "\ud800"}, {"value": "x" * 16385}):
            with self.assertRaises(ValidationError):
                sign_login(self.headers, params)

    def test_empty_parameter_value_and_unicode_value(self):
        self.assertEqual(len(sign_authenticated(b"key", self.headers, {"cycles": ""})), 64)
        self.assertEqual(len(sign_authenticated(b"key", self.headers, {"name": "caf\u00e9"})), 64)

