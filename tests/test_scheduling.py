import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from leapmotor_cloud.scheduling import local_start
from leapmotor_cloud.command_contracts import prepare
from leapmotor_cloud.errors import ValidationError


class SchedulingTests(unittest.TestCase):
    def test_explicit_zone_required(self):
        for zone in (None,'','invalid/zone',False):
            with self.assertRaises(ValidationError):local_start('2026-09-26 12:00:00',zone)

    def test_normal_time_and_distinct_zones(self):
        for zone,hour in [('Europe/Rome',10),('UTC',12),('Asia/Tokyo',3)]:
            self.assertEqual(local_start('2026-09-26 12:00:00',zone).astimezone(timezone.utc).hour,hour)

    def test_dst_gap_and_overlap_rejected(self):
        for value in ('2026-03-29 02:30:00','2026-10-25 02:30:00'):
            with self.assertRaises(ValidationError):local_start(value,'Europe/Rome')

    def test_contract_uses_supplied_clock_and_zone(self):
        v=SimpleNamespace(vin='SYNTHETIC',car_type='B10',is_shared=False,
            raw={'vin':'SYNTHETIC','carType':'B10','abilities':[9]})
        entry=dict(days=[],set_id='offline',start_time='2026-09-26 12:00:00',
            update_time=1790424000000,on='1',circle='in',mode='cold',operate='auto',
            position='all',temperature='22',windlevel='1',wshld='0')
        now=datetime(2026,9,26,11,tzinfo=timezone.utc)
        self.assertEqual(prepare('171',{'controls':[entry]},v,timezone_name='UTC',now=now)['controls'][0],entry)
        with self.assertRaises(ValidationError):
            prepare('171',{'controls':[entry]},v,timezone_name='Europe/Rome',now=now)
        with self.assertRaises(ValidationError):prepare('171',{'controls':[entry]},v,now=now)
