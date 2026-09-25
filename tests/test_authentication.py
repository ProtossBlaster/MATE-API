import json
import socket
import unittest
from datetime import timedelta
from unittest.mock import Mock,patch
from fake_transport import FakeTransport,CERTS,NOW,login_data
from leapmotor_cloud.authentication import LoginClient,LoginUnavailable,LOGIN_PATH
from leapmotor_cloud.transport import Response
from leapmotor_cloud.signing import sign_login

class LoginTests(unittest.TestCase):
    def setUp(self):
        self.fake=FakeTransport();self.now=NOW;self.provider=Mock(return_value=CERTS)
        self.client=LoginClient(self.fake,application_cert=CERTS,account_certificate_provider=self.provider,
                                clock=lambda:self.now,nonce_factory=lambda:'123')
        self.validation=patch('leapmotor_cloud.authentication.certificate_usable',return_value=True)
        self.validation.start();self.addCleanup(self.validation.stop)
        p=patch.object(socket,'socket',side_effect=AssertionError('Network forbidden'));p.start();self.addCleanup(p.stop)

    def queue(self,**kw):
        data=login_data({'exp':(NOW+timedelta(hours=1)).timestamp()})
        data['accessToken']=data.pop('token');data.update(kw)
        self.fake.queue_json({'code':0,'result':0,'data':data})

    def test_request_and_session(self):
        self.queue();s=self.client.login('synthetic-user','synthetic-password',device_id='synthetic-device')
        r=self.fake.requests[0];body=json.loads(r.body)
        self.assertTrue(r.url.endswith(LOGIN_PATH));self.assertEqual(len(self.fake.requests),1)
        core={k:r.headers[k] for k in ('source','channel','acceptLanguage','version','deviceType','nonce','timestamp','deviceId')}
        self.assertEqual(r.headers['sign'],sign_login(core,body))
        self.assertEqual(body['identifierType'],'2');self.assertEqual(s.expires_at,NOW+timedelta(minutes=30))
        self.assertNotIn('synthetic-password',repr(r));self.assertNotIn(s.token,repr(s))

    def test_no_provider_on_rejection(self):
        self.fake.queue_json({'code':5,'data':{'secret':'do-not-print'}})
        with self.assertRaises(LoginUnavailable) as caught:self.client.login('u','p',device_id='d')
        self.provider.assert_not_called();self.assertNotIn('do-not-print',str(caught.exception))

    def test_timeout_no_retry_and_cooldown(self):
        self.fake.on_send=Mock(side_effect=TimeoutError('private-data'))
        for _ in range(2):
            with self.assertRaises(LoginUnavailable):self.client.login('u','p',device_id='d')
        self.assertEqual(len(self.fake.requests),1)

    def test_invalid_application_pair_no_network(self):
        with patch('leapmotor_cloud.authentication.certificate_usable',return_value=False):
            with self.assertRaises(LoginUnavailable):self.client.login('u','p',device_id='d')
        self.assertFalse(self.fake.requests)

    def test_invalid_account_pair_no_session(self):
        self.queue()
        with patch('leapmotor_cloud.authentication.certificate_usable',side_effect=[True,False]):
            with self.assertRaises(LoginUnavailable):self.client.login('u','p',device_id='d')

    def test_provider_failure_sanitized(self):
        self.queue();self.provider.side_effect=RuntimeError('private-key-and-password')
        with self.assertRaises(LoginUnavailable) as caught:self.client.login('u','p',device_id='d')
        self.assertNotIn('private-key',str(caught.exception))

    def test_expired_during_provider(self):
        self.queue()
        def slow(data):self.now+=timedelta(hours=2);return CERTS
        self.provider.side_effect=slow
        with self.assertRaises(LoginUnavailable):self.client.login('u','p',device_id='d')

    def test_duplicate_keys_rejected(self):
        self.fake.responses.append(Response(200,b'{"code":0,"code":5,"data":{}}'))
        with self.assertRaises(LoginUnavailable):self.client.login('u','p',device_id='d')
        self.provider.assert_not_called()

    def test_malformed_signing_material_before_provider(self):
        self.queue(signParam={})
        with self.assertRaises(LoginUnavailable):self.client.login('u','p',device_id='d')
        self.provider.assert_not_called()

if __name__=='__main__':unittest.main()
