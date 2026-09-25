import base64
import unittest
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
from leapmotor_cloud.pin import encrypt_operate_password
from leapmotor_cloud.errors import ValidationError

class PinTests(unittest.TestCase):
    def test_known_token_blocks(self):
        # MD5('a'*32)[8:24] and MD5('b'*32)[8:24], independent fixed fixtures.
        token='a'*32+'b'*32
        encrypted=base64.b64decode(encrypt_operate_password('012345',token))
        import hashlib
        key=hashlib.md5(b'a'*32).hexdigest()[8:24].encode()
        iv=hashlib.md5(b'b'*32).hexdigest()[8:24].encode()
        dec=Cipher(algorithms.AES(key),modes.CBC(iv)).decryptor()
        raw=dec.update(encrypted)+dec.finalize()
        unpad=padding.PKCS7(128).unpadder()
        self.assertEqual(unpad.update(raw)+unpad.finalize(),b'012345')

    def test_invalid_pin(self):
        for pin in (None,'','1a','-1','1'*33,'１２３４',True):
            with self.subTest(pin=pin),self.assertRaises(ValidationError):encrypt_operate_password(pin,'a'*64)

    def test_no_static_fallback(self):
        for token in (None,'','a'*63,True):
            with self.subTest(token=token),self.assertRaises(ValidationError):encrypt_operate_password('1234',token)

    def test_different_token_changes_ciphertext(self):
        self.assertNotEqual(encrypt_operate_password('1234','a'*64),encrypt_operate_password('1234','b'*64))
