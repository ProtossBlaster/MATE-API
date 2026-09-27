"""V3 commands are for every model, and the cloud is the authority on what is permitted.

The first qualification of this library was deliberately narrow: only a B10 could send a
command, because only a B10 had been driven on-car. That narrowness was never a property of
the protocol. `appremotectl` v3 is the single command path of the updated Leapmotor cloud and
of the app shipped on the stores for every model, and the reply carries the cloud's own verdict:
a command a model does not have comes back refused with `result: 40` (无此权限) without the
vehicle moving. So the local gate is the data the cloud itself publishes per vehicle —
`abilities`, `rightList`, `moduleRights` — and never the model name.

What stays model-shaped is the PAYLOAD, because the cars genuinely disagree: the B10 obeys a
bare `{"operate":"off"}` and ignores the full body, the T03 obeys `operate: "off"` only inside
the full seven-field body and ignores the bare form (both measured on-car: the B10 on
2026-06-06, the T03 by @derekzoli on 06-07/08/2026, each confirmed by re-reading acSwitch and
watching the climate actually stop). A contract that reshaped either one would silently turn a
working command into an accepted no-op.
"""
import json
import unittest
from types import SimpleNamespace

from leapmotor_cloud.command_contracts import COMMAND_RULES, prepare
from leapmotor_cloud.errors import ValidationError

# Command IDs, rights and abilities are three independent namespaces: the sunshade is cmd 240
# but right 161, so a test that confuses them proves nothing. Read them from the contract.
SUNSHADE_RIGHT, SUNSHADE_ABILITY = COMMAND_RULES['240']
CLIMATE_RIGHT, CLIMATE_ABILITY = COMMAND_RULES['170']
SENTINEL_RIGHT, SENTINEL_ABILITY = COMMAND_RULES['220']
DECLARED = tuple(a for a in (SUNSHADE_ABILITY, CLIMATE_ABILITY) if a is not None)

# Byte-identical to poller/main.py and web/command_client.py in Mate, where a test already
# holds those two literals equal: the page and Home Assistant must not disagree about one car.
T03_AC_OFF_BODY = ('{"circle":"out","mode":"wind","operate":"off","position":"all",'
                   '"temperature":"26","windlevel":"3","wshld":"0"}')


def vehicle(*, model, rights=None, abilities=DECLARED, shared=False,
            modules=None, rudder='left'):
    raw = dict(vin='SYNTHETIC', carType=model, rightList=rights, moduleRights=modules,
               abilities=list(abilities))
    return SimpleNamespace(vin='SYNTHETIC', car_type=model, raw=raw, is_shared=shared,
                           rudder=rudder, has_right=lambda code: code in (rights or []),
                           has_module_right=lambda code: code in (modules or []))


class EveryModelTests(unittest.TestCase):
    MODELS = ('B10', 'C10', 'C11', 'T03', 'B05', 'C16', 'UNRECOGNISED')

    def test_every_model_may_send_a_command_its_cloud_data_allows(self):
        for model in self.MODELS:
            with self.subTest(model=model):
                self.assertEqual(prepare('240', {'value': '10'},
                                         vehicle(model=model, rights=[SUNSHADE_RIGHT])), {'value': '10'})

    def test_the_owner_omission_exception_is_not_the_b10_privilege(self):
        """bindcars may omit rightList for the account's own car, on any model.

        The official app then derives the owner's permissions from `abilities` — it is one app
        for the whole range, so keying that on the model was conservatism, not evidence.
        """
        for model in self.MODELS:
            with self.subTest(model=model):
                self.assertEqual(prepare('240', {'value': '10'}, vehicle(model=model)),
                                 {'value': '10'})

    def test_the_cloud_data_still_decides_for_every_model(self):
        for model in self.MODELS:
            with self.subTest(model=model):
                # An explicit, empty right list is the cloud saying no.
                with self.assertRaises(ValidationError):
                    prepare('240', {'value': '10'}, vehicle(model=model, rights=[]))
                # An absent ability is the cloud saying the car has no such function.
                with self.assertRaises(ValidationError):
                    prepare('240', {'value': '10'},
                            vehicle(model=model, rights=[SUNSHADE_RIGHT],
                                    abilities=[CLIMATE_ABILITY]))
                # A shared car never gets the owner's omission exception.
                with self.assertRaises(ValidationError):
                    prepare('240', {'value': '10'}, vehicle(model=model, shared=True))


class ClimateShapeTests(unittest.TestCase):
    def test_the_t03_full_off_body_survives_untouched(self):
        state = prepare('170', json.loads(T03_AC_OFF_BODY), vehicle(model='T03', rights=[CLIMATE_RIGHT]))
        self.assertEqual(state, json.loads(T03_AC_OFF_BODY))
        self.assertEqual(state['mode'], 'wind',
                         'rewriting wind to nohotcold changes the body the T03 was measured to obey')

    def test_the_b10_bare_off_stays_bare(self):
        self.assertEqual(prepare('170', {'operate': 'off'}, vehicle(model='B10', rights=[CLIMATE_RIGHT])),
                         {'operate': 'off'})

    def test_close_becomes_off_without_reshaping_the_body(self):
        """`close` is accepted and ignored by every car measured; `off` is the one that acts."""
        body = dict(json.loads(T03_AC_OFF_BODY), operate='close')
        self.assertEqual(prepare('170', body, vehicle(model='T03', rights=[CLIMATE_RIGHT])),
                         json.loads(T03_AC_OFF_BODY))

    def test_a_full_off_body_is_still_validated(self):
        for key, bad in (('windlevel', '9'), ('wshld', '3'), ('circle', 'sideways'),
                         ('temperature', '99'), ('mode', 'invented')):
            with self.subTest(field=key):
                body = dict(json.loads(T03_AC_OFF_BODY), **{key: bad})
                with self.assertRaises(ValidationError):
                    prepare('170', body, vehicle(model='T03', rights=[CLIMATE_RIGHT]))

    def test_turning_the_climate_on_keeps_the_measured_ventilation_rewrite(self):
        body = dict(json.loads(T03_AC_OFF_BODY), operate='manual')
        self.assertEqual(prepare('170', body, vehicle(model='B10', rights=[CLIMATE_RIGHT]))['mode'],
                         'nohotcold')


class ClimateIsNotAbilityGatedTests(unittest.TestCase):
    """A car that under-declares its climate must not lose its climate.

    The European T03 omits AC_ON (ability 6) and cools anyway — measured on-car and reported
    across the ecosystem (Mate #67), which is why Mate's own ability whitelist deliberately
    leaves climate out: "the T03 omits AC_ON (6) yet cools, so its declarations lie there".
    An ability gate on command 170/171 would therefore hide the most used function of the model
    we are opening the door for. The account right and the cloud's own refusal stay in force.
    """

    def test_climate_keeps_its_documented_code_but_is_not_gated_on_it(self):
        from leapmotor_cloud.command_contracts import ABILITY_NOT_GATED
        for cmd in ('170', '171'):
            self.assertIsNotNone(COMMAND_RULES[cmd][1], cmd)   # documentation is kept
            self.assertIn(cmd, ABILITY_NOT_GATED, cmd)         # the gate is off

    def test_a_car_that_omits_ac_on_still_gets_its_climate(self):
        for model in ('T03', 'B10', 'C10'):
            with self.subTest(model=model):
                car = vehicle(model=model, rights=[CLIMATE_RIGHT], abilities=[SUNSHADE_ABILITY])
                self.assertEqual(prepare('170', {'operate': 'off'}, car), {'operate': 'off'})

    def test_the_account_right_still_gates_the_climate(self):
        with self.assertRaises(ValidationError):
            prepare('170', {'operate': 'off'},
                    vehicle(model='T03', rights=[], abilities=[SUNSHADE_ABILITY]))


class SentinelTests(unittest.TestCase):
    """Sentry mode is a V1 command Mate has always offered; V3 must not drop it.

    Its V1 contract is not guesswork: the shipped client sends cmd 220 with
    `{"value":"1"}`/`{"value":"0"}` and declares right 220 (leapmotor_api models.py,
    VehicleRight.SENTRY_MODE = 220) — the same right Mate's own capability profile records.
    No ability code for it was ever identified in the app, so the account right, the control
    module and the cloud's own refusal are what gate it. Command 400 stays unavailable: the
    app's examined availability path disables it, and that is evidence, not a gap.
    """

    def test_the_sentinel_is_sent_with_its_v1_contract(self):
        for value in ('0', '1'):
            for model in ('B10', 'T03', 'C10'):
                with self.subTest(value=value, model=model):
                    self.assertEqual(prepare('220', {'value': value},
                                             vehicle(model=model, rights=[SENTINEL_RIGHT])), {'value': value})

    def test_the_sentinel_rejects_anything_but_its_two_values(self):
        for bad in ('2', 'on', '', True, 1):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    prepare('220', {'value': bad}, vehicle(model='B10', rights=[SENTINEL_RIGHT]))

    def test_the_sentinel_still_obeys_the_cloud(self):
        with self.assertRaises(ValidationError):
            prepare('220', {'value': '1'}, vehicle(model='B10', rights=[]))

    def test_command_400_stays_unavailable(self):
        with self.assertRaises(ValidationError):
            prepare('400', {'value': '1'}, vehicle(model='B10', rights=[SENTINEL_RIGHT]))


if __name__ == '__main__':
    unittest.main()
