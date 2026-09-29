"""Two of the three charge flags are the car's, not ours. Its own value goes back unchanged.

leapmotor-mate #343, @jcconca. 4.7.1 made the refusal name the flag and what it held, so that a
diagnostics bundle would carry the answer with no extra cloud call. It did, four days later:

    2026-09-29 22:12:08 [ERROR] MQTT: command charge_schedule failed:
        Command not sent: invalid charge flag circulation=2

So the flag is `circulation`, the value is **2**, and it is a real C10 publishing it — not
`recharge`, which is what everyone had assumed. His last accepted send was 27/09 at 22:00 with
`circulation=1`; every nightly automation since has failed.

🔑 cmd 190 re-sends the car's WHOLE plan. Only `chargeEnable` and `chargesoc` are the caller's to
choose; `circulation` and `recharge` are read out of the car's `config.3` and written straight back.
Refusing an integer the car itself published, against a domain of {0,1} that was never measured but
assumed, stops the owner from changing the one field they did ask about.

An integer is still required, and only an integer: `None`, `''`, `'1'`, `1.0` and booleans mean the
value could not be read, and echoing something Mate cannot read is a different thing from echoing
something the car said. `chargeEnable` keeps the 0/1 rule — it is a switch, and it is ours.
"""
import unittest

from leapmotor_cloud.command_contracts import charge
from leapmotor_cloud.errors import ValidationError


class CarOwnedFlagTests(unittest.TestCase):

    BASE = dict(chargeEnable=1, chargesoc=90, circulation=1, cycles='1,1,1,1,1,1,1',
                endtime='15:00', recharge=0, starttime='11:00')

    def refusal(self, **over):
        state = dict(self.BASE)
        state.update(over)
        with self.assertRaises(ValidationError) as caught:
            charge(state)
        return str(caught.exception)

    def test_the_value_his_car_publishes_is_sent_back(self):
        """The exact frame from his bundle."""
        state = dict(self.BASE, circulation=2)
        self.assertEqual(charge(state)['circulation'], 2)

    def test_any_integer_the_car_owns_goes_through(self):
        for key in ('circulation', 'recharge'):
            for value in (0, 1, 2, 3, 7, -1):
                state = dict(self.BASE)
                state[key] = value
                self.assertEqual(charge(state)[key], value, (key, value))

    def test_a_value_that_could_not_be_read_is_still_refused_by_name(self):
        """Not every non-0/1 is the car speaking: these are Mate failing to read it."""
        for key in ('circulation', 'recharge'):
            for value in (None, '', '1', 1.0, True, False, [], {}):
                message = self.refusal(**{key: value})
                self.assertIn(key, message, (key, value))
                self.assertIn(repr(value), message, (key, value))

    def test_the_switch_that_is_ours_keeps_its_two_values(self):
        """`chargeEnable` turns the owner's plan on and off. Nothing reads it off the car to echo
        it back unchanged, so there is no value beyond 0 and 1 to be faithful to."""
        for value in (2, -1, 7):
            self.assertIn('chargeEnable', self.refusal(chargeEnable=value))


if __name__ == '__main__':
    unittest.main()
