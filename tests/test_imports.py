"""Every add-on module must at least load: a broken line in one that only some runs
import (whereto.py, in 1.30.0) crashed every scan on the Xbox while all tests passed."""
import importlib
import sys
import types
import unittest
from pathlib import Path

ADDON = Path(__file__).resolve().parents[1] / "addon" / "script.kodisorter"


class EveryModuleLoads(unittest.TestCase):
    def test_import_all(self):
        for n in ("xbmc", "xbmcgui", "xbmcaddon", "xbmcvfs"):
            sys.modules.setdefault(n, types.ModuleType(n))
        sys.path.insert(0, str(ADDON))
        for f in sorted(ADDON.glob("*.py")):
            if f.stem == "default":
                continue  # runs main() on import; loaded by test_library_folders.load_default
            with self.subTest(module=f.stem):
                importlib.import_module(f.stem)

    def test_default_loads(self):
        import tempfile
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from test_library_folders import load_default
        with tempfile.TemporaryDirectory() as d:
            m = load_default(d)
            import whereto  # what TitleFixer imports at the start of every scan
            self.assertTrue(callable(whereto.english_title))
            self.assertTrue(callable(m.TitleFixer))


if __name__ == "__main__":
    unittest.main()
