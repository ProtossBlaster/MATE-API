"""The T03's windows: ability 36 and the 0-100 scale (leapmotor-mate #400).

A European T03 declares 36 and not 12 - two diagnostics bundles, the same list - and every window
command Mate 4.10 was asked for on it ended with «Command not sent: ability_absent for 230». The same
car had sent cmd 230 with 4, 11, 66, 99, 72 and 100 under the earlier library, each answered by the
cloud with code 0. That library already named both codes, 12 WINDOWS_C10 and 36 WINDOWS_T03, and only the
first was copied here. So the gate takes either, and the range follows the code the car declares:
36 is the T03's 0-100 scale, 12 the 0-10 one Mate sends the B10, C10 and B05.
"""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from leapmotor_cloud.capabilities import evaluate
from leapmotor_cloud.command_contracts import COMMAND_RULES, prepare, require
from leapmotor_cloud.errors import ValidationError
from leapmotor_cloud.models import Availability, CapabilitySnapshot, VehicleIdentity

T03 = [1, 2, 3, 5, 7, 10, 11, 14, 15, 17, 18, 20, 30, 31, 34, 35, 36, 52, 61]   # #400, as declared
B10 = [1, 2, 3, 5, 6, 7, 10, 11, 12, 13, 14, 15, 19, 20, 21, 23, 24, 29, 30, 31, 32, 34, 35, 38,
       42, 43, 47, 48, 51, 52, 53, 57, 59, 60, 61, 69, 70]


def car(abilities, model):
    raw = dict(vin='SYNTHETIC', carType=model, rightList=None, moduleRights=None, abilities=abilities)
    return SimpleNamespace(vin='SYNTHETIC', car_type=model, raw=raw, is_shared=False, rudder='left',
                           has_right=lambda code: False, has_module_right=lambda code: False)


class T03WindowsTests(unittest.TestCase):
    def test_a_t03_may_move_its_windows(self):
        require(car(T03, 'T03'), '230')

    def test_a_t03_sends_the_values_it_carried_out(self):
        for value in ('0', '4', '9', '11', '20', '66', '72', '99', '100'):
            with self.subTest(value=value):
                self.assertEqual(prepare('230', {'value': value}, car(T03, 'T03')), {'value': value})
        with self.assertRaises(ValidationError) as caught:
            prepare('230', {'value': '101'}, car(T03, 'T03'))
        self.assertIn('0..100', str(caught.exception))

    def test_a_car_on_twelve_keeps_its_ten_steps(self):
        self.assertEqual(prepare('230', {'value': '10'}, car(B10, 'B10')), {'value': '10'})
        with self.assertRaises(ValidationError) as caught:
            prepare('230', {'value': '20'}, car(B10, 'B10'))
        self.assertIn('0..10', str(caught.exception))

    def test_a_car_with_neither_code_is_still_refused(self):
        with self.assertRaises(ValidationError) as caught:
            require(car([1, 2, 3], 'B10'), '230')
        self.assertIn('ability_absent for 230', str(caught.exception))

    def test_the_planner_takes_either_code(self):
        right, ability = COMMAND_RULES['230']
        now = datetime.now(timezone.utc)
        for declared in ({12}, {36}):
            snapshot = CapabilitySnapshot(VehicleIdentity('SYNTHETIC', 'B10'), frozenset(declared),
                                          frozenset({230}), frozenset({200}), True, True, now)
            decision = evaluate(snapshot, ability=ability, right=right, now=now,
                                max_age=timedelta(minutes=5))
            self.assertIs(decision.state, Availability.AVAILABLE, declared)
        snapshot = CapabilitySnapshot(VehicleIdentity('SYNTHETIC', 'B10'), frozenset({1}),
                                      frozenset({230}), frozenset({200}), True, True, now)
        self.assertIs(evaluate(snapshot, ability=ability, right=right, now=now,
                               max_age=timedelta(minutes=5)).state, Availability.UNSUPPORTED)


if __name__ == '__main__':
    unittest.main()
