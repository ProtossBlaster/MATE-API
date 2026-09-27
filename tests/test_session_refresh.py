"""Renewing a session instead of buying a new one with a login.

Measured against the live cloud on 27/09/2026, on the account Mate's lab runs:

    login  -> data carries accessToken, refreshToken, tokenExpireTime 7200,
              refreshTokenExpireTime 604799, signParam, base64Cert, accountId, …
    POST /base/base-user/token/v1/refresh  {"refreshToken": …}
        -> HTTP 200 code 0 SUCCESS, data: accessToken (a different one), refreshToken,
           signParam, encryptParam, tokenExpireTime, refreshTokenExpireTime, accountId

Two things this settles. The access token lives **two hours**, not the thirty minutes this
client caps every session at — a cap chosen when nothing said otherwise. And the cloud renews
it from a refresh token that lasts **seven days**, returning a whole new session, signing
parameters included, without a login and without re-issuing the account certificate.

For Mate that is the difference between a login every half hour — 48 a day on an account the
cloud has been rationing since 17 September — and one a week.

The cap is not simply deleted: where the cloud states `tokenExpireTime`, that is the bound;
where it says nothing, the old thirty minutes stand, because then nothing has told us better.
"""
import json
import socket
import unittest
from datetime import timedelta
from unittest.mock import Mock, patch

from fake_transport import FakeTransport, CERTS, NOW, login_data
from leapmotor_cloud.authentication import LoginClient, LoginUnavailable, REFRESH_PATH
from leapmotor_cloud.errors import ValidationError
from leapmotor_cloud.signing import sign_authenticated


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeTransport()
        self.now = NOW
        self.client = LoginClient(self.fake, application_cert=CERTS,
                                  account_certificate_provider=Mock(return_value=CERTS),
                                  clock=lambda: self.now, nonce_factory=lambda: '123')
        validation = patch('leapmotor_cloud.authentication.certificate_usable', return_value=True)
        validation.start(); self.addCleanup(validation.stop)
        blocked = patch.object(socket, 'socket', side_effect=AssertionError('Network forbidden'))
        blocked.start(); self.addCleanup(blocked.stop)

    def _data(self, **kw):
        data = login_data({'exp': (NOW + timedelta(hours=3)).timestamp()})
        data['accessToken'] = data.pop('token')
        data.update(kw)
        return data

    def _logged_in(self, **kw):
        self.fake.queue_json({'code': 0, 'result': 0, 'data': self._data(**kw)})
        return self.client.login('synthetic-user', 'synthetic-password', device_id='synthetic-device')

    # ── what the login answer actually carries ───────────────────────────────────────────────
    def test_the_session_keeps_the_refresh_token_the_cloud_sends(self):
        session = self._logged_in(refreshToken='synthetic-refresh',
                                  tokenExpireTime=7200, refreshTokenExpireTime=604799)
        self.assertEqual(session.refresh_token, 'synthetic-refresh')
        self.assertEqual(session.refresh_expires_at, NOW + timedelta(seconds=604799))
        self.assertNotIn('synthetic-refresh', repr(session))

    def test_the_token_lives_as_long_as_the_cloud_says(self):
        """Two hours, not the half hour this client used to impose on every session."""
        session = self._logged_in(refreshToken='r', tokenExpireTime=7200)
        self.assertEqual(session.expires_at, NOW + timedelta(seconds=7200))

    def test_without_a_stated_lifetime_the_old_half_hour_stands(self):
        session = self._logged_in()
        self.assertEqual(session.expires_at, NOW + timedelta(minutes=30))
        self.assertIsNone(session.refresh_token)

    def test_a_lifetime_that_is_not_a_number_is_refused_not_guessed(self):
        for bad in ('soon', True, -1, 0, 10 ** 12):
            with self.subTest(bad=bad):
                with self.assertRaises(LoginUnavailable):
                    self._logged_in(refreshToken='r', tokenExpireTime=bad)

    # ── the renewal itself ───────────────────────────────────────────────────────────────────
    def test_refresh_asks_the_cloud_with_the_refresh_token_and_signs_it(self):
        session = self._logged_in(refreshToken='synthetic-refresh', tokenExpireTime=7200)
        self.fake.queue_json({'code': 0, 'result': 0,
                              'data': self._data(refreshToken='next-refresh', tokenExpireTime=7200)})
        self.now = NOW + timedelta(hours=1)
        renewed = self.client.refresh(session, device_id='synthetic-device')

        request = self.fake.requests[-1]
        self.assertTrue(request.url.endswith(REFRESH_PATH))
        self.assertEqual(json.loads(request.body), {'refreshToken': 'synthetic-refresh'})
        core = {k: request.headers[k] for k in ('source', 'channel', 'acceptLanguage', 'version',
                                                'deviceType', 'nonce', 'timestamp', 'deviceId')}
        self.assertEqual(request.headers['sign'],
                         sign_authenticated(session.key, core, {'refreshToken': 'synthetic-refresh'}))
        self.assertEqual(request.headers['token'], session.token)
        self.assertEqual(request.headers['userId'], session.user_id)
        self.assertEqual(renewed.refresh_token, 'next-refresh')
        self.assertEqual(renewed.expires_at, self.now + timedelta(seconds=7200))
        # The account certificate is not re-issued by a renewal: the session keeps the one it has.
        self.assertEqual(renewed.client_cert, session.client_cert)

    def test_a_renewal_never_reaches_for_the_account_certificate_provider(self):
        session = self._logged_in(refreshToken='r', tokenExpireTime=7200)
        provider = Mock(side_effect=AssertionError('a renewal must not re-issue material'))
        self.client._provider = provider
        self.fake.queue_json({'code': 0, 'result': 0, 'data': self._data(refreshToken='r2', tokenExpireTime=7200)})
        self.client.refresh(session, device_id='synthetic-device')
        provider.assert_not_called()

    def test_a_session_without_a_refresh_token_cannot_be_renewed_and_asks_nothing(self):
        session = self._logged_in()
        with self.assertRaises(ValidationError):
            self.client.refresh(session, device_id='synthetic-device')
        self.assertEqual(len(self.fake.requests), 1)      # the login only

    def test_a_refused_renewal_raises_and_keeps_nothing(self):
        """`302010219 Token refresh error` is what the cloud answers a refresh token it will not
        take. It must surface as a failure, not as a session quietly left as it was."""
        session = self._logged_in(refreshToken='r', tokenExpireTime=7200)
        self.fake.queue_json({'code': 302010219, 'message': 'Token refresh error', 'data': None})
        with self.assertRaises(LoginUnavailable):
            self.client.refresh(session, device_id='synthetic-device')

    def test_an_expired_refresh_token_is_not_sent(self):
        session = self._logged_in(refreshToken='r', tokenExpireTime=7200, refreshTokenExpireTime=604799)
        self.now = NOW + timedelta(seconds=604800)
        with self.assertRaises(ValidationError):
            self.client.refresh(session, device_id='synthetic-device')
        self.assertEqual(len(self.fake.requests), 1)


if __name__ == '__main__':
    unittest.main()
