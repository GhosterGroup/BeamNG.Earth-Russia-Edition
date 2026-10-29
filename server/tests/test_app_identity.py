"""The fork's Windows app identity stays distinct from the upstream release."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import build_app  # noqa: E402


class AppIdentityTest(unittest.TestCase):
    def test_windows_artifact_name_is_fork_specific(self):
        self.assertEqual(build_app.NAME, "BeamNG.Earth-Russia-Edition")

    def test_windows_file_metadata_names_russia_edition(self):
        with tempfile.TemporaryDirectory() as d:
            build_app.version_files(d, "1.7.1-beta")
            metadata = Path(d, "version_info.txt").read_text(encoding="utf-8")
        self.assertIn("ProductName', 'BeamNG.Earth Russia Edition'", metadata)
        self.assertIn("OriginalFilename', 'BeamNG.Earth-Russia-Edition-1.7.1-beta.exe'", metadata)


if __name__ == "__main__":
    unittest.main()
