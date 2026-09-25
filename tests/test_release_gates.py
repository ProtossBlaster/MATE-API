"""Offline release-gate cases. No cloud credentials or physical actuation."""
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
import test_certificates as fixtures
from fake_transport import client_pair,NOW,VIN,session
from leapmotor_cloud.capabilities import evaluate
from leapmotor_cloud.command_contracts import prepare
from leapmotor_cloud.models import CapabilitySnapshot,VehicleIdentity,Availability
from leapmotor_cloud.operating_availability import OperatingState,operating_decision
from leapmotor_cloud.b10_planner import plan_b10
from leapmotor_cloud.vehicle_data import normalize_telemetry
from leapmotor_cloud.session import SessionStore,AuthenticationRequired
from leapmotor_cloud.transport import Response
from leapmotor_cloud.certificates import AccountCertificateManager,CertificateUnavailable
from leapmotor_cloud.material_cleanup import retire_generations
from leapmotor_cloud.errors import ValidationError


class PolicyParityTests(unittest.TestCase):
    def setUp(self):self.now=datetime.now(timezone.utc)

    def test_owner_shared_absent_empty_and_explicit_matrix(self):
        for owner in (True,False):
            for rights in (None,[],[110]):
                for modules in (None,[],[200]):
                    with self.subTest(owner=owner,rights=rights,modules=modules):
                        raw=dict(vin='SYNTHETIC',carType='B10',rightList=rights,moduleRights=modules,abilities=[1])
                        v=SimpleNamespace(vin='SYNTHETIC',car_type='B10',is_shared=not owner,raw=raw,
                            has_right=lambda c:c in (rights or []),has_module_right=lambda c:c in (modules or []))
                        snap=CapabilitySnapshot(VehicleIdentity('SYNTHETIC','B10'),frozenset({1}),
                            frozenset(rights or []),frozenset(modules or []),owner,True,self.now,
                            rights_present=rights is not None,module_rights_present=modules is not None)
                        decision=evaluate(snap,ability=1,right=110,now=self.now,max_age=timedelta(minutes=5))
                        if decision.state is Availability.AVAILABLE:
                            self.assertEqual(prepare('110',{'value':'lock'},v),{'value':'lock'})
                        else:
                            with self.assertRaises(ValidationError):prepare('110',{'value':'lock'},v)

    def test_owner_omission_not_extended_to_other_models(self):
        snap=CapabilitySnapshot(VehicleIdentity('SYNTHETIC','T03'),frozenset({1}),frozenset(),
            frozenset(),True,True,self.now,False,False)
        self.assertNotEqual(evaluate(snap,ability=1,right=110,now=self.now,max_age=timedelta(minutes=5)).state,
                            Availability.AVAILABLE)

    def test_stale_opt_in_and_motion_matrix(self):
        for stale in (False,True):
            for allow in (False,True):
                for driving,on3 in ((False,False),(True,False),(False,True),(None,False),(False,None)):
                    state=OperatingState('SYNTHETIC',self.now-timedelta(hours=2) if stale else self.now,driving,on3)
                    decision=operating_decision(state,now=self.now,state_max_age=timedelta(seconds=60),allow_stale_parked=allow)
                    expected=driving is False and on3 is False and (not stale or allow)
                    self.assertEqual(decision.state is Availability.AVAILABLE,expected)

    def test_planner_honors_stale_opt_in_without_claiming_live_state(self):
        snap=CapabilitySnapshot(VehicleIdentity('SYNTHETIC','B10'),frozenset({1}),frozenset({110}),
            frozenset({200}),True,True,self.now)
        state=OperatingState('SYNTHETIC',self.now-timedelta(hours=2),False,False)
        args=dict(action='doors',value='lock',now=self.now,capability_max_age=timedelta(minutes=5),state_max_age=timedelta(seconds=60))
        self.assertIsNone(plan_b10(snap,state,**args).payload)
        plan=plan_b10(snap,state,allow_stale_parked=True,**args)
        self.assertIsNotNone(plan.payload)
        self.assertIn('not_current',plan.decision.reason)

    def test_cloud_timestamp_cannot_freshen_vehicle(self):
        old=self.now-timedelta(days=2)
        data=dict(vin='SYNTHETIC',collectTime=int(self.now.timestamp()*1000),signalMap={'1':str(int(old.timestamp()*1000))})
        value=normalize_telemetry(data,expected_vin='SYNTHETIC',received_at=self.now)
        self.assertLess(abs((value.observed_at-old).total_seconds()),0.001)
        self.assertLess(abs((value.cloud_collected_at-self.now).total_seconds()),0.001)
        data['signalMap']={}
        self.assertIsNone(normalize_telemetry(data,expected_vin='SYNTHETIC',received_at=self.now).observed_at)

    def test_boolean_and_fractional_capabilities_rejected(self):
        for abilities in ([True],[1.5],['1.5']):
            v=SimpleNamespace(vin='SYNTHETIC',car_type='B10',is_shared=False,
                raw=dict(vin='SYNTHETIC',carType='B10',abilities=abilities))
            with self.assertRaises(ValidationError):prepare('110',{'value':'lock'},v)


class RevocationTests(unittest.TestCase):
    def test_old_rejection_cannot_invalidate_new_session(self):
        store=SessionStore();old=session();new=session(expires_at=NOW+timedelta(hours=1))
        store.replace(old);store.replace(new)
        self.assertFalse(store.invalidate(old));self.assertIs(store.get(NOW),new)
        self.assertTrue(store.invalidate(new))
        with self.assertRaises(AuthenticationRequired):store.get(NOW)

    def test_http401_invalidates_without_retry(self):
        client,fake,store=client_pair();fake.responses.append(Response(401,b'not-json'))
        with self.assertRaises(AuthenticationRequired):client.resolve_vehicle_route(VIN)
        with self.assertRaises(AuthenticationRequired):store.get(NOW)
        self.assertEqual(len(fake.requests),1)

    def test_permission_denial_does_not_revoke_session(self):
        client,fake,store=client_pair();original=store.get(NOW)
        fake.responses.append(Response(403,b'permission-denied'))
        with self.assertRaises(AuthenticationRequired):client.resolve_vehicle_route(VIN)
        self.assertIs(store.get(NOW),original)

    def test_revoked_certificate_not_fallback_on_provider_failure(self):
        fixture=fixtures.CertificateTests();fixture.setUp()
        bundle=fixture.bundle();calls=[]
        def provider():
            calls.append(1)
            if len(calls)>1:raise RuntimeError('private-provider-failure')
            return bundle
        manager=AccountCertificateManager(provider,clock=lambda:fixture.now)
        self.addCleanup(manager.close)
        old=manager.ensure();self.assertTrue(manager.invalidate(old))
        self.assertTrue(all(p.exists() for p in old.paths))
        for _ in range(2):
            with self.assertRaises(CertificateUnavailable):manager.ensure()
        self.assertEqual(len(calls),2)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)/'private';self.root.mkdir(mode=0o700)
        self.old=self.generation('old');self.current=self.generation('current')

    def generation(self,name):
        p=self.root/('generation-'+name);p.mkdir(mode=0o700)
        (p/'cert.pem').write_text('synthetic');(p/'key.pem').write_text('synthetic')
        return p

    def retire(self,paths,**kwargs):
        return retire_generations(self.root,paths,active_paths=[self.current/'cert.pem'],**kwargs)

    def test_quiescence_required(self):
        with self.assertRaises(ValidationError):self.retire([self.old])
        self.assertTrue(self.old.exists())

    def test_explicit_retired_generation_only_and_idempotence(self):
        self.assertEqual(self.retire([self.old],quiescent=True),1)
        self.assertTrue(self.current.exists())
        self.assertEqual(self.retire([self.old],quiescent=True),0)

    def test_active_rejected_before_any_deletion(self):
        with self.assertRaises(ValidationError):self.retire([self.old,self.current],quiescent=True)
        self.assertTrue(self.old.exists());self.assertTrue(self.current.exists())

    def test_symlink_and_unexpected_file_rejected(self):
        extra=self.old/'unexpected';extra.write_text('keep')
        with self.assertRaises(ValidationError):self.retire([self.old],quiescent=True)
        extra.unlink();(self.old/'key.pem').unlink()
        (self.old/'key.pem').symlink_to(self.current/'key.pem')
        with self.assertRaises(ValidationError):self.retire([self.old],quiescent=True)
        self.assertTrue((self.current/'key.pem').exists())

    def test_outside_root_rejected(self):
        with self.assertRaises(ValidationError):self.retire([self.root.parent/'generation-other'],quiescent=True)
