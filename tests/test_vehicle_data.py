import unittest
from datetime import datetime, timedelta, timezone

from leapmotor_cloud.vehicle_data import normalize_telemetry, normalize_configuration
from leapmotor_cloud.operating_availability import OperatingState, front_seat_ventilation_availability
from leapmotor_cloud.models import VehicleIdentity, CapabilitySnapshot, Availability
from leapmotor_cloud.errors import ValidationError


class VehicleDataTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 25, tzinfo=timezone.utc)
        self.args = dict(expected_vin='SYNTHETIC', received_at=self.now)

    def test_pressures_and_precise_soc(self):
        d = normalize_telemetry({'vin':'SYNTHETIC','signalMap':{
            '2646':236,'2653':236,'2660':239,'2667':242,'1204':86,'100003':86.2}}, **self.args)
        self.assertEqual([d.values[k+'_pressure_kpa'] for k in
                         ('front_left','front_right','rear_left','rear_right')], [236,236,239,242])
        self.assertEqual(d.values['precise_soc_percent'],86.2)

    def test_unknowns_preserved_immutable_and_private_repr(self):
        source={'vin':'SYNTHETIC','signalMap':{'100004':1,'future':{'v':[2]}}}
        d=normalize_telemetry(source,**self.args)
        source['signalMap']['future']['v'].append(3)
        self.assertEqual(d.unknown_signals['future']['v'],(2,))
        with self.assertRaises(TypeError):d.raw['signalMap']['100004']=2
        self.assertNotIn('SYNTHETIC',repr(d))
        self.assertNotIn('100004',repr(d))

    def test_absent_and_invalid_not_zero(self):
        for value in (None,True,'nan',255,-1):
            d=normalize_telemetry({'vin':'SYNTHETIC','signalMap':{'1204':value}},**self.args)
            self.assertIsNone(d.values['soc_percent'])
            self.assertIsNone(d.values['front_left_pressure_kpa'])

    def test_separate_times_and_charge_values(self):
        stamp=int((self.now-timedelta(days=2)).timestamp()*1000)
        d=normalize_configuration({'vin':'SYNTHETIC','config':{'3':{
            'percent':100,'isEnable':1,'beginTime':'01:50','endTime':'12:00',
            'cycles':'1,0,0,0,0,0,0','updateTime':stamp}}},**self.args)
        self.assertIsNone(d.observed_at)
        self.assertEqual(d.group_times['3'],self.now-timedelta(days=2))
        with self.assertRaises(TypeError):
            d.group_times['3']=self.now
        self.assertEqual(d.charge['cycles_sunday_first'],(True,False,False,False,False,False,False))
        self.assertEqual(d.charge['begin_time_raw'],'01:50')
        self.assertIsNone(d.charge['timezone'])

    def test_envelope_and_identity(self):
        for response in ({'code':1,'data':{'vin':'SYNTHETIC','signalMap':{}}},
                         {'code':True,'data':{'vin':'SYNTHETIC','signalMap':{}}},
                         {'vin':'OTHER','signalMap':{}}, {'vin':'SYNTHETIC','signal':{}}):
            with self.assertRaises(ValidationError):normalize_telemetry(response,**self.args)
        d=normalize_telemetry({'code':0,'data':{'vin':'SYNTHETIC','signalMap':{}}},**self.args)
        self.assertIsNone(d.observed_at)

    def test_unknown_config_and_malformed_schedule(self):
        d=normalize_configuration({'vin':'SYNTHETIC','config':{
            '3':{'cycles':'1,1','isEnable':'unknown','updateTime':'unknown'},'99':{'future':7}}},**self.args)
        self.assertIsNone(d.charge['cycles_sunday_first'])
        self.assertIsNone(d.charge['enabled'])
        self.assertIsNone(d.group_times['3'])
        self.assertEqual(d.raw['config']['99']['future'],7)

    def test_signal_timestamp_not_receipt(self):
        d=normalize_telemetry({'vin':'SYNTHETIC','signalMap':{'1':1790343174088}},**self.args)
        self.assertNotEqual(d.observed_at,d.received_at)

    def test_raw_datetime_remains_invalid(self):
        with self.assertRaises(ValidationError):
            normalize_configuration({'vin':'SYNTHETIC','config':{
                '3':{'updateTime':self.now}}},**self.args)


class OperatingAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,9,25,tzinfo=timezone.utc)
        self.snapshot=CapabilitySnapshot(VehicleIdentity('SYNTHETIC','B10'),frozenset({42}),
            frozenset({370}),frozenset({200}),True,True,self.now)

    def evaluate(self,state,**kwargs):
        args=dict(position='left_front',rudder='left',now=self.now,
                  capability_max_age=timedelta(minutes=5),state_max_age=timedelta(seconds=30))
        args.update(kwargs)
        return front_seat_ventilation_availability(self.snapshot,state,**args)

    def test_rudder_and_ability(self):
        state=OperatingState('SYNTHETIC',self.now,False,False)
        self.assertEqual(self.evaluate(state).state,Availability.AVAILABLE)
        self.assertEqual(self.evaluate(state,rudder='right').state,Availability.UNSUPPORTED)
        self.assertEqual(self.evaluate(state,rudder='right',position='right_front').state,Availability.AVAILABLE)

    def test_temporary_and_unknown(self):
        for driving,on3 in ((True,False),(False,True)):
            self.assertEqual(self.evaluate(OperatingState('SYNTHETIC',self.now,driving,on3)).state,
                             Availability.TEMPORARILY_UNAVAILABLE)
        for timestamp,driving in ((None,False),(self.now-timedelta(minutes=1),False),(self.now,None)):
            self.assertEqual(self.evaluate(OperatingState('SYNTHETIC',timestamp,driving,False)).state,
                             Availability.UNKNOWN)

    def test_cross_vehicle_rejected(self):
        with self.assertRaises(ValidationError):
            self.evaluate(OperatingState('OTHER',self.now,False,False))
