"""Siberian map styling is confined to Russia and includes the initial test cities."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class WinterRegionTest(unittest.TestCase):
    def test_region_module_is_available(self):
        self.assertIsNotNone(importlib.util.find_spec("winter_regions"),
                             "winter region lookup must be part of the server package")

    def test_initial_siberian_cities_are_inside_winter_region(self):
        if importlib.util.find_spec("winter_regions") is None:
            self.fail("winter_regions module is not implemented")
        import winter_regions
        for name, lon, lat in (("Irkutsk", 104.281, 52.287), ("Markova", 104.183, 52.209),
                               ("Novosibirsk", 82.935, 55.008), ("Yakutsk", 129.732, 62.028)):
            with self.subTest(name=name):
                self.assertTrue(winter_regions.is_siberia(lon, lat))

    def test_neighbouring_countries_and_western_russia_are_unchanged(self):
        if importlib.util.find_spec("winter_regions") is None:
            self.fail("winter_regions module is not implemented")
        import winter_regions
        for name, lon, lat in (("Ulaanbaatar", 106.905, 47.921), ("Astana", 71.430, 51.170),
                               ("Moscow", 37.618, 55.751), ("Berlin", 13.405, 52.520)):
            with self.subTest(name=name):
                self.assertFalse(winter_regions.is_siberia(lon, lat))


if __name__ == "__main__":
    unittest.main()
