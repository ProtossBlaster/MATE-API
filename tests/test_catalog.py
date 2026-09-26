import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from leapmotor_cloud import ValidationError, load_reference_catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "catalog.json"
        self.row = dict(action="set_charge_limit", cmd_id="190", required_right=340, requires_pin=True)

    def load(self, rows):
        self.path.write_text(json.dumps({"registry": rows}), encoding="utf-8")
        return load_reference_catalog(self.path)

    def test_same_command_different_right_preserved(self):
        entries = self.load([self.row, dict(self.row, action="battery_preheat", required_right=190)])
        self.assertIsInstance(entries, tuple)
        self.assertEqual([e.cmd_id for e in entries], ["190", "190"])
        self.assertEqual([e.required_right for e in entries], [340, 190])

    def test_no_evidence_promotion_or_executable_payload_import(self):
        entry, = self.load([dict(self.row, evidence="cloud_verified", cmd_content="untrusted")])
        self.assertEqual(entry.evidence, "legacy_inventory_unverified")
        self.assertFalse(hasattr(entry, "cmd_content"))
        with self.assertRaises(FrozenInstanceError):
            entry.evidence = "cloud_verified"

    def test_duplicate_action_rejected(self):
        with self.assertRaises(ValidationError):
            self.load([self.row, self.row])

    def test_missing_fields(self):
        for name in self.row:
            with self.subTest(field=name):
                with self.assertRaises(ValidationError):
                    self.load([{k: v for k, v in self.row.items() if k != name}])

    def test_invalid_field_types(self):
        for changes in ({"requires_pin": 1}, {"cmd_id": 190}, {"cmd_id": "../secret"},
                        {"action": ""}, {"action": "shell;command"},
                        {"required_right": True}, {"required_right": -1}):
            with self.assertRaises(ValidationError):
                self.load([dict(self.row, **changes)])

    def test_null_right_and_empty_registry(self):
        self.assertIsNone(self.load([dict(self.row, required_right=None)])[0].required_right)
        self.assertEqual(self.load([]), ())

    def test_bad_json_shapes_and_duplicate_json_keys(self):
        for raw in (b"{", b"[]", b"{}", b'{"registry":{}}', b'{"registry":[null]}',
                    b'{"registry":[],"registry":[]}', b"\xff"):
            self.path.write_bytes(raw)
            with self.assertRaises(ValidationError):
                load_reference_catalog(self.path)

    def test_size_limit_and_missing_path(self):
        self.path.write_bytes(b" " * (1024 * 1024 + 1))
        with self.assertRaises(ValidationError):
            load_reference_catalog(self.path)
        with self.assertRaises(ValidationError) as error:
            load_reference_catalog(self.path.parent / "PRIVATE-PATH")
        self.assertNotIn("PRIVATE-PATH", str(error.exception))
        with self.assertRaises(ValidationError):
            load_reference_catalog(str(self.path))

    def test_real_reference_inventory_has_64_unique_unverified_actions(self):
        parents = Path(__file__).resolve().parents
        if len(parents) < 4:
            self.skipTest("External diagnostic inventory not included in a standalone package copy")
        root = parents[3]
        reference = root / "outputs/leapmotor-app-analysis/mate_command_registry_baseline_2026-09-25.json"
        if not reference.is_file():
            self.skipTest("External diagnostic inventory not included in a standalone package copy")
        with patch("socket.socket", side_effect=AssertionError("Network forbidden")):
            entries = load_reference_catalog(reference)
        self.assertEqual(len(entries), 64, "Reference inventory drift requires review")
        self.assertEqual(len({e.action for e in entries}), 64)
        self.assertTrue(all(e.evidence == "legacy_inventory_unverified" for e in entries))
