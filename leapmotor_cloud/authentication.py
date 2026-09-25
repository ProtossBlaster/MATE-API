"""Single-attempt login with explicit TLS material; no legacy SDK or persistence.

Application provisioning and account-PKCS12 decoding are caller responsibilities.
A coordinator must serialize logins across processes sharing the same account.
"""
import json
from datetime import timedelta
from threading import Lock
from .cloud import GLOBAL_ORIGIN, _unique_object, _invalid_constant
from .certificate_validation import certificate_usable
from .errors import ValidationError
from .models import require_aware
from .session import CloudSession, _expiry_from_token
from .signing import sign_login
from .transport import Request, Response, MAX_RESPONSE_BYTES, validate_cert_paths

LOGIN_PATH = '/base/base-user/account/v1/login'


class LoginUnavailable(RuntimeError):
    def __init__(self):
        super().__init__('Cloud login unavailable; no automatic retry')


class LoginClient:
    def __init__(self, transport, *, application_cert, account_certificate_provider,
                 clock, nonce_factory, language='en-US'):
        validate_cert_paths(application_cert)
        if not all(callable(x) for x in (account_certificate_provider, clock, nonce_factory)):
            raise ValidationError('Explicit certificate provider, clock and nonce required')
        self._transport, self._application_cert = transport, application_cert
        self._provider, self._clock, self._nonce = account_certificate_provider, clock, nonce_factory
        self._language, self._lock, self._next_attempt = language, Lock(), None

    def login(self, username, password, *, device_id):
        for value in (username,password,device_id):
            if not isinstance(value,str) or not value or len(value)>16384:
                raise ValidationError('Missing or invalid login input')
        with self._lock:
            now=self._clock();require_aware(now)
            if self._next_attempt is not None and now<self._next_attempt:
                raise LoginUnavailable()
            if not certificate_usable(*self._application_cert,now=now):
                raise LoginUnavailable()
            nonce=self._nonce()
            if not isinstance(nonce,str) or not nonce.isascii() or not nonce.isdecimal() or len(nonce)>32:
                raise ValidationError('Invalid login nonce')
            body=dict(identifier=username,identifierType='2',security=password)
            core=dict(source='leapmotor',channel='1',acceptLanguage=self._language,
                      version='V1.16.4-1',deviceType='android',nonce=nonce,
                      timestamp=str(int(now.timestamp()*1000)),deviceId=device_id)
            headers=dict(core,sign=sign_login(core,body),carvin='',cartype='')
            headers.update({'Content-Type':'application/json','x-region':'EU',
                            'x-api-signature-version':'2.0','X-P12_ENC_ALG':'1'})
            request=Request('POST',GLOBAL_ORIGIN+LOGIN_PATH,headers,
                            json.dumps(body,separators=(',',':')).encode())
            self._next_attempt=now+timedelta(seconds=60)
            try:
                response=self._transport.send(request,client_cert=self._application_cert)
                if not isinstance(response,Response) or response.status!=200 or len(response.body)>MAX_RESPONSE_BYTES:
                    raise ValueError()
                envelope=json.loads(response.body.decode(),object_pairs_hook=_unique_object,parse_constant=_invalid_constant)
                if not isinstance(envelope,dict):raise ValueError()
                codes=[envelope[k] for k in ('code','result') if k in envelope]
                if not codes or any(type(c)is bool or str(c)!='0' for c in codes):raise ValueError()
                data=envelope.get('data')
                if not isinstance(data,dict):raise ValueError()
                token=data.get('accessToken')
                if not isinstance(token,str) or not token:raise ValueError()
                observed=self._clock();require_aware(observed)
                expiry=_expiry_from_token(token)
                expiry=min(observed+timedelta(minutes=30),expiry) if expiry else observed+timedelta(minutes=30)
                if expiry<=observed:raise ValueError()
                # Validate token/signing structure before invoking the material provider.
                normalized=dict(data,token=token)
                CloudSession.from_login_data(normalized,device_id=device_id,
                                             client_cert=self._application_cert,expires_at=expiry)
                pair=self._provider(data)
                validate_cert_paths(pair)
                finished=self._clock();require_aware(finished)
                if not certificate_usable(*pair,now=finished):raise ValueError()
                session=CloudSession.from_login_data(normalized,device_id=device_id,
                                                    client_cert=pair,expires_at=expiry)
                session.ensure_valid(finished)
                return session
            except Exception:
                raise LoginUnavailable() from None
