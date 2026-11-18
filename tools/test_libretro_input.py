#!/usr/bin/env python3
"""Verify scripted libretro input intervals used by menu integration tests."""
import argparse
import unittest

from test_megacd_libretro import button_event, event_pressed


class LibretroInputTests(unittest.TestCase):
    def test_buttons_are_independent_and_intervals_are_half_open(self):
        events = [button_event('10:down:3'), button_event('12:start:2')]
        self.assertFalse(event_pressed(events, 9, 5))
        self.assertTrue(event_pressed(events, 10, 5))
        self.assertTrue(event_pressed(events, 12, 5))
        self.assertTrue(event_pressed(events, 12, 3))
        self.assertFalse(event_pressed(events, 13, 5))
        self.assertTrue(event_pressed(events, 13, 3))
        self.assertFalse(event_pressed(events, 14, 3))

    def test_rejects_bad_button_or_range(self):
        for value in ('4:nope:2', '-1:up:4', '4:up:0', 'x:up:4', '4:start'):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                button_event(value)


if __name__ == '__main__':
    unittest.main()
