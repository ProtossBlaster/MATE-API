import subprocess
import sys
import unittest
from types import SimpleNamespace
from leapmotor_cloud.command_contracts import prepare,require
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

    def test_non_b10_not_advertised_as_supported(self):
        with self.assertRaises(ValidationError):prepare('240',{'value':'10'},self.vehicle(model='T03',rights=[240]))

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
