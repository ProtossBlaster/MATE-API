import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from leapmotor_cloud.b10_reads import B10ReadClient
from leapmotor_cloud.b10_payloads import prepare_b10
from leapmotor_cloud.session import CloudSession, SessionStore
from leapmotor_cloud.transport import Response
from leapmotor_cloud.errors import ValidationError


class ReadsTests(unittest.TestCase):
    def setUp(self):
        self.requests=[]
        self.now=datetime(2026,9,25,tzinfo=timezone.utc)
        store=SessionStore()
        store.replace(CloudSession('synthetic','user','device',b'x'*32,(Path('/fake/cert'),Path('/fake/key'))))
        self.client=B10ReadClient(self,store,center='https://appgateway.leapmotor-international.de',
            region='https://appgateway.leapmotor-international.de',clock=lambda:self.now)
        self.override=None

    def send(self,request,*,client_cert):
        self.requests.append(request)
        if self.override is not None:return self.override
        if request.method=='GET':
            data={'vin':'SYNTHETIC','config':{'3':{'percent':100,'isEnable':1}}}
        else:data={'vin':'SYNTHETIC','signalMap':{'2646':236,'2667':242,'100004':1}}
        return Response(200,json.dumps({'code':0,'data':data}).encode())

    def test_two_reads_and_normalizers(self):
        bundle=self.client.read('SYNTHETIC')
        self.assertEqual(bundle.telemetry.values['front_left_pressure_kpa'],236)
        self.assertEqual(bundle.configuration.charge['limit_percent'],100)
        self.assertEqual(bundle.telemetry.unknown_signals['100004'],1)
        self.assertEqual(len(self.requests),2)
        query=parse_qs(urlsplit(self.requests[1].url).query)
        self.assertEqual(query['osType'],['Android'])
        self.assertEqual(query['appVersion'],['V1.16.4-1'])
        self.assertTrue(all('/appremotectl' not in r.url for r in self.requests))

    def test_http_and_api_errors_not_retried(self):
        for result in (Response(401,b'{}'),Response(200,b'{"code":1,"data":{}}'),
                       Response(200,b'{"code":0,"code":1,"data":{}}'),
                       Response(200,b'{"vin":"SYNTHETIC","signalMap":{}}')):
            self.override=result
            before=len(self.requests)
            with self.assertRaises(ValidationError):self.client.telemetry('SYNTHETIC')
            self.assertEqual(len(self.requests),before+1)

    def test_invalid_identity_before_network(self):
        with self.assertRaises(ValidationError):self.client.read('bad\nVIN')
        self.assertFalse(self.requests)


class PayloadTests(unittest.TestCase):
    def payload(self,action,**kwargs):
        return json.loads(prepare_b10(action,model='B10',**kwargs).state)

    def test_windows(self):
        for p,v in ((0,'0'),(20,'2'),(50,'5'),(100,'10')):
            self.assertEqual(self.payload('windows',value=p),{'value':v})

    def test_doors_and_trunk(self):
        self.assertEqual(self.payload('doors',value='lock'),{'value':'lock'})
        self.assertEqual(self.payload('trunk',value=False),{'value':'false'})

    def test_seats_and_wheel(self):
        for action in ('seat_heat','seat_ventilation'):
            for p in ('left_front','right_front'):
                for level in (0,1):
                    self.assertEqual(self.payload(action,position=p,value=level),{'position':p,'level':str(level)})
        self.assertEqual(self.payload('wheel_heat',value=True),{'level':'2'})
        self.assertEqual(self.payload('wheel_heat',value=False),{'level':'1'})

    def test_climate(self):
        self.assertEqual(self.payload('climate',value='off'),{'operate':'off'})
        self.assertEqual(self.payload('climate',value='ventilation26')['mode'],'nohotcold')
        self.assertEqual(self.payload('climate',value='auto22')['operate'],'auto')

    def test_unverified_combinations_blocked(self):
        for action,kwargs in [('windows',{'value':30}),('windows',{'value':True}),
            ('seat_heat',{'value':3,'position':'left_front'}),('climate',{'value':'wind'}),
            ('autopark',{}),('trunk',{'value':'false'})]:
            with self.assertRaises(ValidationError):prepare_b10(action,model='B10',**kwargs)
        with self.assertRaises(ValidationError):prepare_b10('windows',model='T03',value=100)
