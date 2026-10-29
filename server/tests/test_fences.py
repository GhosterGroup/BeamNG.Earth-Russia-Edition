import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fences
import mapgeom


class FenceClassificationTest(unittest.TestCase):
    def test_overture_class_and_osm_tags_select_shared_styles(self):
        def features(cls, tags, subtype="barrier"):
            return SimpleNamespace(attrs={"class": np.array([cls]), "subtype": np.array([subtype]),
                                          "tags": np.array([json.dumps(tags)])})

        self.assertEqual(fences.fence_kind(features("fence", {"barrier": "fence", "fence_type": "metal"}), 0),
                         "metal")
        self.assertEqual(fences.fence_kind(features("fence", {"barrier": "fence", "fence_type": "chain_link"}), 0),
                         "chainlink")
        self.assertEqual(fences.fence_kind(features("wall", {"barrier": "wall", "material": "brick"}), 0), "wall")
        self.assertEqual(fences.fence_kind(features("gate", {"barrier": "gate"}), 0), "gate")
        self.assertIsNone(fences.fence_kind(features("guard_rail", {"barrier": "guard_rail"}), 0))


class FencePlacementTest(unittest.TestCase):
    class Frame:
        @staticmethod
        def enu_to_geodetic(x, y, z):
            return np.asarray(x), np.asarray(y), np.asarray(z)

    @staticmethod
    def elev(lat, lon):
        return np.zeros_like(np.asarray(lat), dtype=np.float64)

    def test_line_rows_are_deterministic_and_tile_clipped(self):
        line = np.array([[-20.0, 30.0], [280.0, 30.0]])
        first = fences._line_rows("feature-1", line, "wood", (0, 0, 256, 256), self.Frame(), self.elev)
        second = fences._line_rows("feature-1", line, "wood", (0, 0, 256, 256), self.Frame(), self.elev)
        self.assertEqual(first, second)
        self.assertTrue(first)
        self.assertTrue(all(0 <= row[1] < 256 and row[2] == 30.0 for row in first))

    def test_modules_keep_clear_of_public_road_envelope(self):
        road = (np.array([[0.0, 0.0]]), np.array([[256.0, 0.0]]), np.array([6.0]))
        blocked = fences._line_rows("a", np.array([[0.0, 0.0], [100.0, 0.0]]), "metal",
                                    (0, -20, 256, 256), self.Frame(), self.elev, road)
        clear = fences._line_rows("a", np.array([[0.0, 20.0], [100.0, 20.0]]), "metal",
                                  (0, -20, 256, 256), self.Frame(), self.elev, road)
        self.assertEqual(blocked, [])
        self.assertTrue(clear)

    def test_tile_output_is_bounded(self):
        line = np.array([[0.0, 50.0], [10000.0, 50.0]])
        class Features:
            ids = np.array(["long"])
            kind = np.array([mapgeom.LINE])
            attrs = {"class": np.array(["fence"]), "subtype": np.array(["barrier"]),
                     "tags": np.array(['{"barrier":"fence","fence_type":"metal"}'])}

            def __len__(self):
                return 1

            @staticmethod
            def parts(i):
                return [[line]]

        with mock.patch.object(fences.mapcells, "cells_for_points", return_value=["cell"]), \
                mock.patch.object(fences.mapgeom, "enu_xy", return_value=(line[:, 0], line[:, 1])):
            rows = fences.tile_rows(self.Frame(), lambda cell: Features(), (0, 0, 10000, 100), self.elev)
        self.assertLessEqual(len(rows), fences.MAX_TILE_ITEMS)


if __name__ == "__main__":
    unittest.main()
