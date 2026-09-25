import json
import subprocess
import sys
import unittest
from dataclasses import replace
from unittest.mock import Mock
from leapmotor_cloud.mate_compat import Vehicle,MateClientCompatibility,MateAPIError,adapter_owned_headers
from leapmotor_cloud.account_password import AccountPasswordResolver
from leapmotor_cloud.command_contracts import prepare
from leapmotor_cloud.errors import ValidationError


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.api=MateClientCompatibility(username='synthetic',password='synthetic',
            app_cert_path='/fake/app.crt',app_key_path='/fake/app.key',timezone_name='UTC')
        self.api._remote_control_raw=Mock()
        self.api.read=Mock()

    def test_vehicle_csv_lists_unknown_codes_and_replace(self):
        source=dict(vin='SYNTHETIC',carType='B10',rightList='110, 230',moduleRights='200',abilities=[1,12,99999],rudder='left')
        v=Vehicle.from_dict(source,True)
        self.assertTrue(v.has_right(230));self.assertTrue(v.has_module_right(200))
        self.assertTrue(v.has_ability(99999));self.assertFalse(v.has_ability(True))
        source['abilities'].append(42);self.assertNotIn(42,v.raw['abilities'])
        self.assertEqual(replace(v,car_type='T03').car_type,'T03')
        self.assertNotIn('SYNTHETIC',repr(v))
        self.assertEqual(prepare('230',{'value':'5'},v),{'value':'5'})

    def test_malformed_capability_list_never_grants_right(self):
        for rights in ([True],[1.5],'110,bad','110,,230'):
            with self.assertRaises(ValidationError):
                Vehicle.from_dict(dict(vin='SYNTHETIC',carType='B10',rightList=rights),True)

    def test_command_convenience_methods_have_native_payloads(self):
        for name,cmd,payload in [('lock_vehicle','110',{'value':'lock'}),
            ('open_trunk','130',{'value':'true'}),('open_sunshade','240',{'value':'10'}),
            ('steering_wheel_heat_on','320',{'level':'2'}),('rearview_mirror_heat_off','440',{'value':'1'})]:
            getattr(self.api,name)('SYNTHETIC')
            sent=self.api._remote_control_raw.call_args.kwargs
            self.assertEqual(sent['cmd_id'],cmd);self.assertEqual(json.loads(sent['cmd_content']),payload)

    def test_unknown_and_incomplete_commands_fail_closed(self):
        for action in ('autopark','fota_install','seat_heat'):
            with self.assertRaises(MateAPIError):self.api._remote_control(vin='SYNTHETIC',action=action)
        self.api._remote_control_raw.assert_not_called()
        with self.assertRaises(MateAPIError):self.api.sentry_mode_on('SYNTHETIC')

    def test_schedule_preserves_explicit_fields(self):
        self.api.set_charge_schedule('SYNTHETIC',enabled=True,soc_limit=90,start_time='01:00',
            end_time='04:00',cycles='1,0,0,0,0,0,0',circulation=1,recharge=1)
        state=json.loads(self.api._remote_control_raw.call_args.kwargs['cmd_content'])
        self.assertEqual(state,dict(chargeEnable=1,chargesoc=90,starttime='01:00',endtime='04:00',
            cycles='1,0,0,0,0,0,0',circulation=1,recharge=1))

    def test_schedule_response_double_json_and_malformed(self):
        self.api.read.return_value={'data':'{"controls":[{"set_id":"synthetic"}]}'}
        self.assertEqual(self.api.get_climate_schedule('SYNTHETIC'),[{'set_id':'synthetic'}])
        self.api.read.return_value={'data':{'controls':'not-a-list'}}
        with self.assertRaises(MateAPIError):self.api.get_climate_schedule('SYNTHETIC')

    def test_message_read_and_no_obsolete_headers(self):
        self.api.read.return_value={'data':{'count':1,'list':[{'title':'synthetic','message':'test','sendTime':1}]}}
        self.assertEqual(self.api.get_message_list().messages[0].title,'synthetic')
        self.assertEqual(adapter_owned_headers(token='private').to_dict(),{})
        with self.assertRaises(MateAPIError):self.api.get_message_list(page_no=True)

    def test_no_legacy_imports(self):
        source='''
import sys,importlib.abc
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0]=='leapmotor_api':raise RuntimeError('Legacy SDK forbidden')
sys.meta_path.insert(0,Block())
from leapmotor_cloud.mate_compat import MateClientCompatibility,Vehicle
from leapmotor_cloud.account_password import AccountPasswordResolver
MateClientCompatibility(username='x',password='x',app_cert_path='/fake/c',app_key_path='/fake/k')
'''
        subprocess.run([sys.executable,'-c',source],check=True,capture_output=True,timeout=10)


class AccountPasswordTests(unittest.TestCase):
    def setUp(self):
        self.resolver=AccountPasswordResolver(round_keys=list(range(32)),sbox=list(range(256)),password_candidates=['synthetic'])

    def test_deterministic_and_private(self):
        first=self.resolver.derive('account-1','uid-1')
        self.assertEqual(first,self.resolver.derive('account-1','uid-1'))
        self.assertEqual(len(first),15)
        self.assertNotEqual(first,self.resolver.derive('account-2','uid-1'))
        self.assertNotIn('synthetic',repr(self.resolver))

    def test_candidate_order_and_explicit_password(self):
        values=self.resolver.candidates({'accountId':'a','uid':'b'},explicit='explicit')
        self.assertEqual(values[0],b'explicit');self.assertEqual(values[-1],b'synthetic')
        self.assertEqual(len(values),3)

    def test_invalid_parameters_and_input(self):
        for keys,table in [([1]*31,list(range(256))),([True]*32,list(range(256))),(list(range(32)),[0]*256)]:
            with self.assertRaises(ValidationError):AccountPasswordResolver(round_keys=keys,sbox=table)
        for account,uid in [(True,'uid'),('a',''),('a',None)]:
            with self.assertRaises(ValidationError):self.resolver.derive(account,uid)
