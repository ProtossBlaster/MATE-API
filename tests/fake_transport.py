import base64
import json
from datetime import datetime, timezone
from pathlib import Path

from leapmotor_cloud.cloud import CENTER_ORIGIN, CloudReadClient
from leapmotor_cloud.session import CloudSession, SessionStore
from leapmotor_cloud.transport import Response

NOW = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)
VIN = "SYNTHETICVIN000001"
CERTS = (Path("synthetic-cert.pem"), Path("synthetic-key.pem"))


def login_data(payload=None):
    encode = lambda value: base64.b64encode(value).decode()
    middle = base64.urlsafe_b64encode(json.dumps({} if payload is None else payload).encode()).decode().rstrip("=")
    return {"token": "e30." + middle + "." + encode(bytes(range(32))),
            "accountId": "synthetic-account",
            "signParam": {"r2": encode(bytes(range(32, 64))), "r3": encode(bytes(range(64, 96)))}}


def session(payload=None, **kwargs):
    return CloudSession.from_login_data(login_data(payload), device_id="synthetic-device", client_cert=CERTS, **kwargs)


class FakeTransport:
    def __init__(self):
        self.responses, self.requests, self.certificates = [], [], []
        self.on_send = None

    def queue_json(self, data):
        self.responses.append(Response(200, json.dumps(data).encode()))

    def route(self, **overrides):
        data = dict(vin=VIN, appCenter=CENTER_ORIGIN, appRegion=CENTER_ORIGIN)
        data.update(overrides)
        self.queue_json({"code": 0, "data": data})

    def send(self, request, *, client_cert):
        self.requests.append(request)
        self.certificates.append(client_cert)
        if self.on_send:
            self.on_send()
        if not self.responses:
            raise AssertionError("Unexpected request")
        return self.responses.pop(0)


def client_pair(value=None, *, clock=lambda: NOW):
    store, fake = SessionStore(), FakeTransport()
    store.replace(value if value is not None else session())
    return CloudReadClient(fake, store, clock=clock, nonce_factory=lambda: "12345.0"), fake, store


def page(rows, *, number=1, total=None, pages=None):
    total = len(rows) if total is None else total
    return {"code": 0, "result": 0, "data": {
        "pageNum": number, "pageSize": 20, "totalPage": (total + 19) // 20 if pages is None else pages,
        "total": total, "list": rows}}
