"""The fan speeds a car declares in its cloud entry (leapmotor-mate #445).

The vehicle list gives each car a `funcConfig` with the range of its remote climate, the fan's in gears:
`{"HVAC": {"fan": {"max": "9", "min": "1", "unit": "gear"}, ...}, "valid": true}`. A B10 lists 1-9 and
its fan reads 9 on the car; a B05 has nine speeds since a software update. The climate contract took
1-7 from every car, so 8 and 9 could not be sent. A higher declared top now opens them, and 1-7 stays
open to every car, because the fixed climate bodies send 7 to all of them.
"""
import tracemalloc
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from leapmotor_cloud.command_contracts import fan_top, prepare
from leapmotor_cloud.errors import ValidationError

B10 = {'HVAC': {'fan': {'max': '9', 'min': '1', 'unit': 'gear'},
                'temperature': {'max': '32', 'min': '18', 'unit': 'celsius'}},
       'valid': True}   # as a B10's vehicle list entry carries it


def car(func_config=None):
    raw = dict(vin='SYNTHETIC', carType='B10', rightList=None, moduleRights=None, abilities=[6])
    if func_config is not None:raw['funcConfig'] = func_config
    return SimpleNamespace(vin='SYNTHETIC', car_type='B10', raw=raw, is_shared=False, rudder='left',
                           has_right=lambda code: False, has_module_right=lambda code: False)


def climate(level):
    return dict(circle='in', mode='cold', operate='manual', position='all', temperature='22',
                windlevel=level, wshld='0')


def fan(**declared):
    return dict(B10, HVAC=dict(B10['HVAC'], fan=dict(B10['HVAC']['fan'], **declared)))


class DeclaredFanSpeedsTests(unittest.TestCase):
    def test_a_car_that_declares_nine_may_send_eight_and_nine(self):
        self.assertEqual(fan_top(B10), 9)
        for level in ('8', '9'):
            with self.subTest(level=level):
                self.assertEqual(prepare('170', climate(level), car(B10))['windlevel'], level)
        with self.assertRaises(ValidationError):prepare('170', climate('10'), car(B10))

    def test_its_schedule_takes_them_too(self):
        entry = dict(climate('9'), days=[], set_id='offline', start_time='2026-09-26 12:00:00',
                     update_time=1790424000000, on='1')
        now = datetime(2026, 9, 26, 11, tzinfo=timezone.utc)
        controls = prepare('171', {'controls': [entry]}, car(B10), timezone_name='UTC', now=now)['controls']
        self.assertEqual(controls[0]['windlevel'], '9')

    def test_a_car_that_declares_none_keeps_one_to_seven(self):
        self.assertEqual(prepare('170', climate('7'), car())['windlevel'], '7')
        with self.assertRaises(ValidationError):prepare('170', climate('8'), car())

    def test_an_unreadable_declaration_keeps_one_to_seven(self):
        for name, config in (('not valid', dict(B10, valid=False)), ('valid as text', dict(B10, valid='true')),
                             ('no valid', {'HVAC': B10['HVAC']}), ('top in words', fan(max='nine')),
                             ('top a fraction', fan(max='9.5')), ('bottom zero', fan(min='0')),
                             ('bottom above top', fan(min='10')), ('fan a list', dict(B10, HVAC={'fan': []})),
                             ('HVAC a list', dict(B10, HVAC=[])), ('not an object', '9'),
                             ('top too long to read', fan(max='9' * 4301))):
            with self.subTest(name):
                self.assertEqual(fan_top(config), 7)
                self.assertEqual(prepare('170', climate('7'), car(config))['windlevel'], '7')
                with self.assertRaises(ValidationError):prepare('170', climate('8'), car(config))

    def test_a_car_that_declares_fewer_still_takes_the_seven_it_is_sent(self):
        self.assertEqual(fan_top(fan(max='5')), 7)
        self.assertEqual(prepare('170', climate('7'), car(fan(max='5')))['windlevel'], '7')

    def test_a_level_is_the_plain_text_of_a_number(self):
        for level in (7, '07', '+7', ' 7', '7 ', '٧', '7.0', 'None', '', '0'):
            with self.subTest(level=level):
                with self.assertRaises(ValidationError):prepare('170', climate(level), car(B10))

    def test_a_huge_declared_top_is_compared_not_listed(self):
        tracemalloc.start()
        try:
            self.assertEqual(prepare('170', climate('1'), car(fan(max='1000000')))['windlevel'], '1')
            with self.assertRaises(ValidationError):prepare('170', climate('1000001'), car(fan(max='1000000')))
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 1_000_000)


if __name__ == '__main__':
    unittest.main()
