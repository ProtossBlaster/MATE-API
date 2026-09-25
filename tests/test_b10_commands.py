import json
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import parse_qs
from leapmotor_cloud.b10_commands import B10CommandClient, interpret
from leapmotor_cloud.models import VehicleIdentity, CapabilitySnapshot
from leapmotor_cloud.operating_availability import OperatingState
from leapmotor_cloud.session import CloudSession, SessionStore
from leapmotor_cloud.transport import Response, TransportError
from leapmotor_cloud.errors import ValidationError


class FakeTransport:
    def __init__(self):
        self.calls=[]
        self.error=False

    def send(self, request, **kwargs):
        self.calls.append(request)
        if self.error:raise TransportError('network')
        return Response(200,b'{"code":0,"data":{"eventId":"test-event","timeout":15}}')


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,9,25,tzinfo=timezone.utc)
        self.transport=FakeTransport()
        sessions=SessionStore()
        sessions.replace(CloudSession(token='test-token',user_id='test-user',device_id='device',
            key=b'x'*32,client_cert=(Path('/cert'),Path('/key')),
            expires_at=self.now+timedelta(hours=1)))
        self.snapshot=CapabilitySnapshot(vehicle=VehicleIdentity('TESTVIN','B10'),
            abilities=frozenset({12}),rights=frozenset({230}),module_rights=frozenset({200}),
            owner=True,complete=True,observed_at=self.now)
        self.state=OperatingState('TESTVIN',self.now,False,False)
        self.client=B10CommandClient(self.transport,sessions,
            region='https://appgateway.leapmotor-international.de',clock=lambda:self.now,
            nonce_factory=lambda:'123',pin_encryptor=lambda pin,token:'ciphertext')

    def run_command(self, **kw):
        args=dict(action='windows',value=20,pin='1234',authorized=True,
                  capability_max_age=timedelta(minutes=5),state_max_age=timedelta(seconds=30))
        args.update(kw)
        return self.client.execute(self.snapshot,self.state,**args)

    def test_payload_and_acceptance(self):
        receipt=self.run_command()
        self.assertEqual(receipt.outcome,'accepted')
        self.assertFalse(receipt.physical_execution_confirmed)
        body=parse_qs(self.transport.calls[0].body.decode())
        self.assertEqual(body['cmdid'],['230'])
        self.assertEqual(json.loads(body['state'][0]),{'value':'2'})
        self.assertEqual(body['oppwd'],['ciphertext'])
        self.assertEqual(receipt.timeout_seconds,15)

    def test_no_authorization_no_request(self):
        with self.assertRaises(ValidationError):self.run_command(authorized=False)
        self.assertEqual(self.transport.calls,[])

    def test_stale_state_no_request(self):
        self.now+=timedelta(minutes=1)
        with self.assertRaises(ValidationError):self.run_command()
        self.assertEqual(self.transport.calls,[])

    def test_network_failure_never_retried(self):
        self.transport.error=True
        receipt=self.run_command()
        self.assertEqual(receipt.outcome,'unknown')
        self.assertFalse(receipt.automatic_retry_allowed)
        self.assertEqual(len(self.transport.calls),1)

    def test_rejected(self):
        self.assertEqual(interpret(Response(200,b'{"code":4}')).outcome,'rejected')

    def test_ambiguous_response(self):
        for body in (b'{}',b'{"code":0,"result":4}',b'{"code":0,"code":4}',b'broken'):
            self.assertEqual(interpret(Response(200,body)).outcome,'unknown')

    def test_missing_event_is_not_completion(self):
        r=interpret(Response(200,b'{"code":0,"data":{}}'))
        self.assertEqual(r.outcome,'accepted_untracked')
        self.assertFalse(r.physical_execution_confirmed)


if __name__=='__main__':unittest.main()
