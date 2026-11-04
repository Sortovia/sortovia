"""Picking a folder on the phone: Kodi Sorter lists the phone's folders itself."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from test_library_folders import load_default  # noqa: E402


class PhoneFolder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d = load_default(os.path.join(self.tmp, "data"))
        tree = {"": ["YouTube", "1DM", ".hidden"], "1DM/": ["Compressed", "Video"], "1DM/Video/": []}
        sys.modules["xbmcvfs"].listdir = lambda p: (tree.get(p[len("dav://x/"):], []), [])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def pick(self, answers):
        seen = []

        class Dlg:
            def select(self, h, opts):
                seen.append((h, opts))
                return answers.pop(0)
        return self.d.pick_phone_folder(Dlg(), "dav://x/"), seen

    def test_go_into_a_folder_and_use_it(self):
        got, seen = self.pick([1, 2, 0])  # 1DM -> Video -> use this folder
        self.assertEqual(got, "1DM/Video/")
        self.assertEqual(seen[0][1], ["Use this folder: Download", "1DM/", "YouTube/"])  # hidden folder left out
        self.assertEqual(seen[2][0], "Phone: Download/1DM/Video")

    def test_back_goes_up_then_whole_share(self):
        got, _ = self.pick([1, -1, -1])  # into 1DM, back up, back at the top
        self.assertEqual(got, "")


if __name__ == "__main__":
    unittest.main()
