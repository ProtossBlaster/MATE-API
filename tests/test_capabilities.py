import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

from leapmotor_cloud import CapabilitySnapshot, ValidationError, VehicleIdentity, evaluate

NOW = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)
AGE = timedelta(minutes=5)


def snapshot(**kwargs):
    base = CapabilitySnapshot(VehicleIdentity("PRIVATE-VIN-A", "B10"), frozenset({42}),
                              frozenset({370}), frozenset({200}), False, True, NOW)
    return replace(base, **kwargs)


class CapabilityTests(unittest.TestCase):
    def decision(self, item, **kwargs):
        return evaluate(item, ability=42, right=370, now=kwargs.get("now", NOW), max_age=AGE)

    def test_model_independent_matrix(self):
        cases = [(True, True, False, True, "available"),
                 (False, True, False, True, "unsupported"),
                 (True, False, False, True, "forbidden"),
                 (False, False, False, False, "unknown"),
                 (True, False, True, True, "unknown")]
        for model in ("B10", "C03", "UNRECOGNIZED"):
            for ability, right, owner, complete, expected in cases:
                with self.subTest(model=model, expected=expected, owner=owner):
                    item = snapshot(vehicle=VehicleIdentity("PRIVATE-VIN", model),
                                    abilities=frozenset({42} if ability else set()),
                                    rights=frozenset({370} if right else set()),
                                    owner=owner, complete=complete)
                    self.assertEqual(self.decision(item).state.value, expected)
                    self.assertEqual(item.vehicle.model, model)

    def test_shared_control_module_denied(self):
        self.assertEqual(self.decision(snapshot(module_rights=frozenset())).reason, "control_module_denied")

    def test_owner_missing_right_is_unknown_not_denied(self):
        self.assertEqual(self.decision(snapshot(owner=True, rights=frozenset())).reason,
                         "owner_rule_not_reconstructed")

    def test_owner_missing_module_is_unknown(self):
        self.assertEqual(self.decision(snapshot(owner=True, module_rights=frozenset())).state.value, "unknown")

    def test_owner_explicit_permissions(self):
        self.assertEqual(self.decision(snapshot(owner=True)).state.value, "available")

    def test_unknown_ownership(self):
        self.assertEqual(self.decision(snapshot(owner=None)).reason, "ownership_unknown")

    def test_expired_and_future(self):
        self.assertEqual(self.decision(snapshot(observed_at=NOW - AGE - timedelta(seconds=1))).reason,
                         "snapshot_expired")
        self.assertEqual(self.decision(snapshot(observed_at=NOW + timedelta(microseconds=1))).reason,
                         "snapshot_from_future")

    def test_freshness_boundary_and_timezone(self):
        item = snapshot(observed_at=NOW - AGE)
        self.assertEqual(self.decision(item).state.value, "available")
        self.assertEqual(self.decision(item, now=NOW.astimezone(timezone(timedelta(hours=2)))).state.value,
                         "available")

    def test_incomplete_positive_data_remains_unknown(self):
        self.assertEqual(self.decision(snapshot(complete=False)).reason, "snapshot_incomplete")

    def test_naive_datetime_and_invalid_age(self):
        with self.assertRaises(ValidationError):
            snapshot(observed_at=NOW.replace(tzinfo=None))
        with self.assertRaises(ValidationError):
            self.decision(snapshot(), now=NOW.replace(tzinfo=None))
        for age in (None, 5, timedelta(0), timedelta(seconds=-1)):
            with self.assertRaises(ValidationError):
                evaluate(snapshot(), ability=42, right=370, now=NOW, max_age=age)

    def test_unknown_codes_preserved_without_inference(self):
        item = snapshot(abilities=frozenset({43, 67, 99999}))
        self.assertEqual(item.abilities, frozenset({43, 67, 99999}))
        self.assertEqual(self.decision(item).state.value, "unsupported")

    def test_repr_does_not_expose_vin(self):
        self.assertNotIn("PRIVATE-VIN-A", repr(snapshot()))
        self.assertNotIn("PRIVATE-VIN-A", repr(snapshot().vehicle))

    def test_immutability_and_vehicle_isolation(self):
        first = snapshot()
        second = snapshot(vehicle=VehicleIdentity("PRIVATE-VIN-B", "B10"), abilities=frozenset())
        with self.assertRaises(FrozenInstanceError):
            first.owner = True
        self.assertEqual(self.decision(first).state.value, "available")
        self.assertEqual(self.decision(second).state.value, "unsupported")

    def test_invalid_identity_codes_flags_and_requirements(self):
        for vin, model in (("", "B10"), (None, "B10"), ("VIN", " ")):
            with self.assertRaises(ValidationError):
                VehicleIdentity(vin, model)
        for kw in ({"abilities": {42}}, {"abilities": frozenset({True})},
                   {"rights": frozenset({-1})}, {"owner": 1}, {"complete": 1}, {"vehicle": None}):
            with self.assertRaises(ValidationError):
                snapshot(**kw)
        for ability, right in ((True, 370), (42, True), (0, 370), (42, "370")):
            with self.assertRaises(ValidationError):
                evaluate(snapshot(), ability=ability, right=right, now=NOW, max_age=AGE)

