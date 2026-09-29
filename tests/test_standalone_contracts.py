import subprocess
import sys
import unittest
from types import SimpleNamespace
from leapmotor_cloud.command_contracts import charge,prepare,require
from leapmotor_cloud.errors import ValidationError

class StandaloneContractTests(unittest.TestCase):
    def vehicle(self, *, shared=False, rights=None, abilities=None, model='B10', rudder='left'):
        raw=dict(vin='SYNTHETIC',carType=model,rightList=rights,moduleRights=None,
                 abilities=[1,12,13,21,42,43] if abilities is None else abilities)
        return SimpleNamespace(vin='SYNTHETIC',car_type=model,raw=raw,is_shared=shared,rudder=rudder,
                               has_right=lambda code:code in (rights or []),has_module_right=lambda code:False)

    def test_owner_omitted_rights(self):
        self.assertEqual(prepare('240',{'value':'10'},self.vehicle()),{'value':'10'})

    def test_shared_missing_rights_denied(self):
        with self.assertRaises(ValidationError):prepare('240',{'value':'10'},self.vehicle(shared=True))

    def test_owner_explicit_empty_rights_denied(self):
        with self.assertRaises(ValidationError):prepare('240',{'value':'10'},self.vehicle(rights=[]))

    def test_ability_absent_denied(self):
        with self.assertRaises(ValidationError):prepare('240',{'value':'10'},self.vehicle(abilities=[1]))

    def test_rudder_maps_driver(self):
        for rudder,physical in [('left','left_front'),('right','right_front')]:
            self.assertEqual(prepare('370',{'position':'driver','level':'1'},self.vehicle(rudder=rudder))['position'],physical)

    def test_windows_all_steps(self):
        for n in range(11):self.assertEqual(prepare('230',{'value':str(n)},self.vehicle()),{'value':str(n)})
        with self.assertRaises(ValidationError):prepare('230',{'value':'11'},self.vehicle())

    def test_no_mate_or_legacy_sdk_import_required(self):
        code='''
import sys, importlib.abc
class Deny(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname.split('.')[0] in {'leapmotor_api','db_reader','crypto','api_v2_bridge'}:
   raise RuntimeError('Forbidden legacy dependency')
sys.meta_path.insert(0,Deny())
from leapmotor_cloud.command_contracts import prepare
from leapmotor_cloud.certificate_validation import certificate_usable
'''
        subprocess.run([sys.executable,'-c',code],check=True,capture_output=True,timeout=10)

if __name__=='__main__':unittest.main()


class ChargeFlagRefusalTests(unittest.TestCase):
    """A refused charge flag says which one, and what it held.

    Three flags travel in cmd 190 and any value of any of them that is not the integer 0 or 1 gave
    one indistinguishable sentence. Two of the three are not the caller's to choose: `circulation`
    and `recharge` are read from the car and written straight back, so a car that publishes anything
    else stopped its owner with a message naming none of the three (leapmotor-mate #343, @jcconca).
    """

    BASE = dict(chargeEnable=1,chargesoc=90,circulation=1,cycles='1,1,1,1,1,1,1',
                endtime='15:00',recharge=0,starttime='11:00')

    def refusal(self,**over):
        state=dict(self.BASE);state.update(over)
        with self.assertRaises(ValidationError) as caught:charge(state)
        return str(caught.exception)

    def test_a_complete_schedule_is_accepted(self):
        self.assertEqual(charge(dict(self.BASE)),self.BASE)

    # An INTEGER the car published is no longer a fault for the two flags Mate only echoes:
    # @jcconca's C10 publishes circulation=2, measured in the bundle this very naming produced.
    # → tests/test_a_flag_read_from_the_car_goes_back_as_the_car_sent_it.py
    UNREADABLE=(None,True,False,'1',1.0,'')

    def test_every_flag_and_value_is_named(self):
        for key in ('chargeEnable','circulation','recharge'):
            values=(2,-1)+self.UNREADABLE if key=='chargeEnable' else self.UNREADABLE
            for value in values:
                message=self.refusal(**{key:value})
                self.assertIn(key,message,(key,value))
                self.assertIn(repr(value),message,(key,value))

    def test_two_different_faults_do_not_read_the_same(self):
        self.assertNotEqual(self.refusal(circulation=None),self.refusal(recharge=None))
        self.assertNotEqual(self.refusal(circulation=None),self.refusal(circulation=''))

    def test_a_day_mask_with_no_days_keeps_its_own_words(self):
        self.assertIn('day',self.refusal(cycles='0,0,0,0,0,0,0'))
