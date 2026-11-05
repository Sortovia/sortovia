#!/usr/bin/env python3
"""Build the public Kodi repository from the add-ons in ../addon.

  python3 tools/build_kodi_repo.py <clone of kodi-repo>

Writes into the target folder (a clone of github.com/akaguyver/kodi-repo):
  addons.xml, addons.xml.md5      - what Kodi reads to find updates
  <id>/<id>-<version>.zip         - one zip per add-on version
  <id>-<version>.zip              - top-level copy of each newest zip, so
                                    Install from zip file can use the web source
  index.html                      - the public landing page; its zip link is what
                                    Kodi's file browser sees
  README.md, CHANGELOG.md, LICENSE.txt - the guide and licence, for the GitHub page

After building: commit and push the target repo. Kodi picks up new versions
on its next update check. Bump the version in addon.xml for every release.
"""
import hashlib
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "addon"
REPO_ID = "repository.akaguyver"


def version_of(xml):
    return re.search(r'<addon[^>]*\sversion="([^"]+)"', xml).group(1)


def build(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    entries, links = [], []
    for addon in sorted(p for p in ROOT.iterdir() if (p / "addon.xml").is_file()):
        xml = (addon / "addon.xml").read_text(encoding="utf-8")
        ver = version_of(xml)
        zpath = out / addon.name / f"{addon.name}-{ver}.zip"
        zpath.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(addon.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    z.write(f, f"{addon.name}/{f.relative_to(addon).as_posix()}")
            if addon.name == "script.kodisorter":
                # The guide and version history shown inside the add-on (welcome screen, Help).
                for doc in ("README.md", "CHANGELOG.md"):
                    z.write(ROOT.parent / doc, f"{addon.name}/resources/{doc}")
                z.write(ROOT.parent / "LICENSE.txt", f"{addon.name}/LICENSE.txt")
        entries.append(re.sub(r"^<\?xml[^>]*\?>\s*", "", xml).strip())
        (zpath.parent / (zpath.name + ".md5")).write_text(
            hashlib.md5(zpath.read_bytes()).hexdigest())
        # Top-level copy of the newest zip of every add-on, so Kodi's
        # "Install from zip file" can pick it straight from the web source.
        for old in out.glob(f"{addon.name}-*.zip"):
            old.unlink()
        top = out / zpath.name
        top.write_bytes(zpath.read_bytes())
        if addon.name == "script.kodisorter":
            # Only the add-on itself: on the Xbox the repository add-on can't connect,
            # so it isn't offered to people as something to install.
            links.append(top.name)
            icon = addon / "icon.png"
            (zpath.parent / "icon.png").write_bytes(icon.read_bytes())
            # Kodi shows these on the add-on's page in its repository browser
            (zpath.parent / "fanart.png").write_bytes((addon / "resources" / "media" / "fanart.png").read_bytes())
        print(f"built {zpath.relative_to(out)}")

    # Phone helper for other people: one-step Termux installer + the scripts it fetches.
    phone = out / "phone"
    phone.mkdir(exist_ok=True)
    for src in (ROOT.parent / "tools" / "phone" / "install.sh", ROOT.parent / "tools" / "kodi_share.sh",
                ROOT.parent / "tools" / "yt_helper.py", ROOT.parent / "tools" / "phone" / "cookies-txt.xpi",
                ROOT.parent / "tools" / "phone" / "index.html"):
        (phone / src.name).write_bytes(src.read_bytes())
    print("built phone/")

    # The logo on the web pages
    brand = ROOT.parent / "brand" / "png"
    assets = out / "assets"
    assets.mkdir(exist_ok=True)
    for src, name in ((brand / "sortovia-logo-horizontal-1200.png", "sortovia-logo-horizontal.png"),
                      (brand / "icon" / "sortovia-icon-64.png", "favicon.png"),
                      (brand / "icon" / "sortovia-icon-256.png", "sortovia-icon.png")):
        (assets / name).write_bytes(src.read_bytes())

    addons_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n'
                  + "\n".join(entries) + "\n</addons>\n")
    (out / "addons.xml").write_text(addons_xml, encoding="utf-8")
    (out / "addons.xml.md5").write_text(hashlib.md5(addons_xml.encode("utf-8")).hexdigest())
    (out / ".nojekyll").write_text("")
    page = (ROOT.parent / "tools" / "site_index.html").read_text(encoding="utf-8")
    (out / "index.html").write_text(page.replace("{{ZIP}}", links[0]), encoding="utf-8")
    for doc in ("README.md", "CHANGELOG.md", "LICENSE.txt"):
        (out / doc).write_bytes((ROOT.parent / doc).read_bytes())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    build(Path(sys.argv[1]))
