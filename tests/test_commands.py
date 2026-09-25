import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import leapmotor_cloud
from leapmotor_cloud import (CapabilitySnapshot, CommandUnavailable, ValidationError,
                            VehicleIdentity, prepare_seat_ventilation)


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)
        self.item = CapabilitySnapshot(VehicleIdentity("PRIVATE-VIN", "B10"), frozenset({42}),
                                       frozenset({370}), frozenset({200}), False, True, self.now)
        guard = patch("socket.socket", side_effect=AssertionError("Network forbidden"))
        guard.start()
        self.addCleanup(guard.stop)

    def prepare(self, item=None, position=1, level=3):
        return prepare_seat_ventilation(self.item if item is None else item, position=position,
                                        level=level, now=self.now, max_age=timedelta(minutes=5))

    def test_legacy_driver_payload_and_evidence(self):
        result = self.prepare()
        self.assertEqual(result.cmd_id, "370")
        self.assertEqual(result.content, '{"value":"1,3"}')
        self.assertEqual(result.evidence, "legacy_payload_simulation_only")
        self.assertEqual(result.decision.state.value, "available")

    def test_all_legacy_levels(self):
        for level in range(4):
            with self.subTest(level=level):
                self.assertEqual(self.prepare(level=level).content, '{"value":"1,' + str(level) + '"}')

    def test_invalid_levels(self):
        for level in (-1, 4, True, False, 1.0, "1", None):
            with self.assertRaises(ValidationError):
                self.prepare(level=level)

    def test_unmapped_or_wrongly_typed_positions(self):
        for position in (0, 2, 3, 6, -1, True, False, 1.0, "1", None):
            with self.assertRaises(ValidationError):
                self.prepare(position=position)

    def test_non_available_decisions_block_preparation(self):
        for item, state in ((replace(self.item, complete=False), "unknown"),
                            (replace(self.item, rights=frozenset()), "forbidden"),
                            (replace(self.item, abilities=frozenset()), "unsupported")):
            with self.subTest(state=state):
                with self.assertRaises(CommandUnavailable) as error:
                    self.prepare(item)
                self.assertEqual(error.exception.decision.state.value, state)
                self.assertNotIn("PRIVATE-VIN", str(error.exception))

    def test_passenger_capability_does_not_enable_driver(self):
        with self.assertRaises(CommandUnavailable):
            self.prepare(replace(self.item, abilities=frozenset({43, 67})))

    def test_no_sender_or_sensitive_fields(self):
        command = self.prepare()
        self.assertFalse(hasattr(leapmotor_cloud, "execute_command"))
        self.assertFalse(hasattr(command, "execute"))
        for field in ("vin", "token", "pin", "device_id"):
            self.assertFalse(hasattr(command, field))
        self.assertNotIn("PRIVATE-VIN", repr(command))

