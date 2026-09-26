"""Mappings checked against the installed original SDK and Mate web generators."""
import unittest
from leapmotor_cloud.mate_compat import Vehicle
from leapmotor_cloud.command_contracts import require,COMMAND_RULES

class OriginalCommandParityTests(unittest.TestCase):
 def test_verified_ability_labels(self):
  # SDK VehicleAbility: LOCK_UNLOCK, FIND_CAR, AC_ON, AC_PRESET, NAVIGATION,
  # CHARGE_LIMIT, UNLOCK_CHARGE_GUN, STEERING_WHEEL, REAR_HEAT.
  for cmd,ability in {'110':10,'120':11,'170':6,'171':9,'180':52,'190':35,'192':48,'320':15,'440':19}.items():
   with self.subTest(cmd=cmd):
    self.assertEqual(COMMAND_RULES[cmd][1],ability)
    v=Vehicle.from_dict(dict(vin='TEST',carType='B10',abilities=[ability]),False)
    require(v,cmd)
 def test_original_sunshade_and_preheat_rights(self):
  self.assertEqual(COMMAND_RULES['240'][0],161)
  self.assertEqual(COMMAND_RULES['160'][0],190)

if __name__=='__main__':unittest.main()
