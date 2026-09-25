import unittest
from datetime import datetime,timedelta,timezone
from leapmotor_cloud.vehicle_data import normalize_telemetry
from leapmotor_cloud.sensor_catalog import BASELINE_SIGNALS
from leapmotor_cloud.b10_planner import plan_b10
from leapmotor_cloud.models import VehicleIdentity,CapabilitySnapshot,Availability
from leapmotor_cloud.operating_availability import OperatingState


class SensorsTests(unittest.TestCase):
    def normalize(self,signals):
        return normalize_telemetry({'vin':'TEST','signalMap':signals},expected_vin='TEST',
                                   received_at=datetime.now(timezone.utc))

    def test_numeric_measurements(self):
        result=self.normalize({'1177':422.7,'1178':-12.5,'1349':'24.5','1318':5684})
        self.assertEqual(result.values['battery_voltage_v'],422.7)
        self.assertEqual(result.values['battery_current_a'],-12.5)
        self.assertEqual(result.values['interior_temperature_c'],24.5)

    def test_codes_are_not_bools_or_percentages(self):
        result=self.normalize({'3727':1,'1816':2,'1938':0,'1941':3,'2183':26})
        self.assertEqual(result.values['front_left_window_position_raw'],1)
        self.assertEqual(result.values['wheel_heating_code'],2)
        self.assertEqual(result.values['climate_switch_code'],0)
        self.assertNotIn('climate_on',result.values)

    def test_unknowns_missing_and_alarm_positions(self):
        result=self.normalize({'100004':1,'2641':1,'2648':0,'2655':2,'2662':3})
        self.assertEqual(result.unknown_signals['100004'],1)
        self.assertIsNone(result.values['battery_min_temperature_c'])
        self.assertEqual(result.values['front_left_tire_alarm_code'],1)
        self.assertEqual(result.values['rear_left_tire_alarm_code'],2)

    def test_every_catalog_id_preserved_and_named(self):
        result=self.normalize({k:0 for k in BASELINE_SIGNALS})
        for k,(name,_,_) in BASELINE_SIGNALS.items():
            self.assertIn(name,result.values)
            self.assertEqual(result.raw['signalMap'][k],0)


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc)
        self.snapshot=CapabilitySnapshot(VehicleIdentity('TEST','B10'),
            frozenset({3,6,10,12,15,21,42,43}),frozenset({110,130,170,230,301,320,370}),
            frozenset({200}),True,True,self.now)
        self.state=OperatingState('TEST',self.now,False,False)

    def plan(self,action,value=None,**kwargs):
        return plan_b10(self.snapshot,self.state,action=action,value=value,now=self.now,
            capability_max_age=timedelta(minutes=5),state_max_age=timedelta(seconds=30),**kwargs)

    def test_prepared_families_have_no_execution(self):
        for action,value in [('doors','lock'),('trunk',False),('windows',20),
                             ('climate','off'),('wheel_heat',False)]:
            result=self.plan(action,value)
            self.assertEqual(result.decision.state,Availability.AVAILABLE)
            self.assertTrue(result.requires_physical_confirmation)
            self.assertIsNotNone(result.payload)
        self.assertIsNotNone(self.plan('seat_heat',1,position='left_front').payload)
        self.assertIsNotNone(self.plan('seat_ventilation',1,position='right_front',rudder='left').payload)

    def test_stale_and_driving_have_no_payload(self):
        self.state=OperatingState('TEST',self.now-timedelta(minutes=1),False,False)
        self.assertIsNone(self.plan('doors','lock').payload)
        self.state=OperatingState('TEST',self.now,True,False)
        self.assertEqual(self.plan('doors','lock').decision.state,Availability.TEMPORARILY_UNAVAILABLE)

    def test_unverified_command_blocked(self):
        self.assertIsNone(self.plan('v2l',True).payload)
        self.assertEqual(self.plan('autopark').decision.state,Availability.UNKNOWN)
