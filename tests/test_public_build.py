"""The public package and web page, as a new user gets them: built for real into a temp folder."""
import hashlib
import os
import re
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_kodi_repo  # noqa: E402


class PublicBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        build_kodi_repo.build(cls.tmp)
        cls.version = re.search(r'<addon[^>]*\sversion="([^"]+)"',
                                (ROOT / "addon/script.kodisorter/addon.xml").read_text()).group(1)
        cls.name = "script.kodisorter-%s.zip" % cls.version
        cls.zip = zipfile.ZipFile(cls.tmp / cls.name)
        cls.members = cls.zip.namelist()

    @classmethod
    def tearDownClass(cls):
        cls.zip.close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_package_has_what_kodi_and_a_new_user_need(self):
        for f in ("addon.xml", "default.py", "icon.png", "LICENSE.txt", "resources/README.md", "resources/CHANGELOG.md",
                  "resources/settings.xml", "resources/language/resource.language.en_gb/strings.po"):
            self.assertIn("script.kodisorter/" + f, self.members)
        self.assertFalse([m for m in self.members if "__pycache__" in m or m.endswith(".pyc")])

    def test_addon_xml_is_valid_and_names_its_icon(self):
        root = ET.fromstring(self.zip.read("script.kodisorter/addon.xml"))
        self.assertEqual(root.findtext(".//assets/icon"), "icon.png")
        self.assertEqual(self.zip.read("script.kodisorter/icon.png")[:8], b"\x89PNG\r\n\x1a\n")

    def test_every_setting_has_its_text_and_a_real_action(self):
        settings = ET.fromstring(self.zip.read("script.kodisorter/resources/settings.xml"))
        po = self.zip.read("script.kodisorter/resources/language/resource.language.en_gb/strings.po").decode()
        labels = [e.get("label") for e in settings.iter() if e.get("label")]
        self.assertTrue(labels)
        for label in labels:
            self.assertIn('msgctxt "#%s"' % label, po)
        src = (ROOT / "addon/script.kodisorter/default.py").read_text(encoding="utf-8")
        for e in settings.iter("setting"):
            if e.get("type") == "action":
                self.assertIn('"%s":' % re.search(r"action=(\w+)", e.get("action")).group(1), src)
            else:
                self.assertIn('setting_on("%s")' % e.get("id"), src)

    def test_web_page_keeps_the_link_kodi_reads(self):
        lines = (self.tmp / "index.html").read_text(encoding="utf-8").splitlines()
        # The exact form the Xbox has always read: one link per line, the text equal to the file.
        self.assertIn('<a href="%s">%s</a><br>' % (self.name, self.name), lines)
        zips = [l for l in lines if re.search(r'href="[^"]*\.zip"', l)]
        self.assertEqual(len(zips), 1)  # a new user can't pick the wrong one
        self.assertFalse([l for l in lines if "{{" in l])

    def test_published_files_exist(self):
        for f in (self.name, "LICENSE.txt", "README.md", "CHANGELOG.md", "addons.xml", "script.kodisorter/icon.png",
                  "phone/install.sh", "phone/kodi_share.sh", "phone/yt_helper.py", "phone/index.html",
                  "phone/get-cookies-txt-locally.xpi"):
            self.assertTrue((self.tmp / f).is_file(), f)
        md5 = (self.tmp / "script.kodisorter" / (self.name + ".md5")).read_text()
        self.assertEqual(md5, hashlib.md5((self.tmp / self.name).read_bytes()).hexdigest())

    def test_nothing_private_is_published(self):
        bad = re.compile(rb"gmail\.com|/ro" rb"ot/kodi|/ro" rb"ot/\.claude|akaguyver/kodi-sorter\b|send Claude|owner's phone|\.config/kodi-sorter-companion")
        published = [p for p in self.tmp.rglob("*") if p.is_file() and p.suffix != ".zip"]
        found = [str(p) for p in published if bad.search(p.read_bytes())]
        found += [m for m in self.members if bad.search(self.zip.read(m))]
        self.assertEqual(found, [])

    def test_guide_only_points_at_public_places(self):
        guide = (ROOT / "README.md").read_text(encoding="utf-8")
        for path in re.findall(r"\]\(([^)#]+)\)", guide):
            if not path.startswith("http"):
                self.assertTrue((self.tmp / path).is_file(), path)
        self.assertNotIn("tools/", guide)


if __name__ == "__main__":
    unittest.main()
