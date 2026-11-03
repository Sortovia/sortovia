"""Welcome screen, "what to sort", the guide and "what's new".

README.md and CHANGELOG.md from the repository are packed into resources/ by
tools/build_kodi_repo.py, so the guide on the TV is the same as on GitHub.
Kodi's text viewer shows plain text with [B]..[/B] tags, so the Markdown is
turned into that (md_to_kodi, pure and tested).
"""
import json
import os
import re

# kind as plan_for reports it (upper case) -> what the person sees
KINDS = [("TV", "TV episodes"), ("MOVIE", "Movies"), ("COMIC", "Comics"), ("TUTORIAL", "Tutorials")]
ALL_KINDS = [k for k, _ in KINDS]


def md_to_kodi(md):
    """Markdown -> text for Kodi's text viewer."""
    out = []
    in_code = False
    for line in md.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            out.append("    " + line)
            continue
        if re.match(r"^\s*-{3,}\s*$", line):
            out.append("")
            continue
        if re.match(r"^\s*\|?\s*:?-{3,}", line):
            continue  # table separator row
        if line.lstrip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            line = "  " + "  -  ".join(c for c in cells if c)
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            text = m.group(2)
            if len(m.group(1)) <= 2:
                out += ["", "[B]%s[/B]" % text.upper(), ""]
            else:
                out += ["", "[B]%s[/B]" % text]
            continue
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)          # [text](link) -> text
        line = re.sub(r"\*\*(.+?)\*\*", r"[B]\1[/B]", line)            # **bold**
        line = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", line)  # *italic*
        line = line.replace("`", "")
        line = re.sub(r"^(\s*)[-*] ", "\\1\u2022 ", line)              # bullets
        out.append(line)
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def changes_since(changelog, old, new):
    """The CHANGELOG lines for versions newer than old, up to new (as Kodi text)."""
    def vt(v):
        return tuple(int(x) for x in re.findall(r"\d+", v or "0")[:3])
    keep = []
    taking = False
    for line in changelog.splitlines():
        m = re.match(r"^-\s+\*\*(\d+\.\d+(?:\.\d+)?)(?:\.x)?\*\*", line)
        if m:
            taking = vt(old) < vt(m.group(1)) <= vt(new)
        elif not line.startswith("  "):
            taking = False  # a heading or blank line ends that version's details
        if taking:
            keep.append(line)
    return md_to_kodi("\n".join(keep)) if keep else ""


_STD = {"TV": "TV", "MOVIE": "Movies", "COMIC": "Comics", "TUTORIAL": "Tutorials"}


def _friendly(path):
    """win-lib://removable/D:\\My Shows/ -> D:\\My Shows"""
    p = re.sub(r"^win-lib://[^/]*/", "", path or "").replace("/", "\\")
    return re.sub(r"\\{2,}", r"\\", p).rstrip("\\") or path


# ---------- Kodi side ----------
def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (IOError, OSError):
        return ""


def _load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return {}


def _save(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=1)
    except (IOError, OSError):
        pass


class Onboarding(object):
    def __init__(self, addon_path, data_path, version, heading):
        self.res = os.path.join(addon_path, "resources")
        self.state_file = data_path
        self.version = version
        self.heading = heading
        self.state = _load(data_path) if data_path else {}

    def wanted(self):
        """Kinds to sort (default: all)."""
        kinds = self.state.get("kinds")
        return [k for k in kinds if k in ALL_KINDS] if kinds else list(ALL_KINDS)

    def wanted_line(self):
        w = self.wanted()
        return "everything" if len(w) == len(ALL_KINDS) else ", ".join(n for k, n in KINDS if k in w)

    def folders(self):
        """{kind: folder} for kinds that go into the person's own existing folders."""
        return dict((k, v) for k, v in (self.state.get("folders") or {}).items() if k in ALL_KINDS and v)

    def folders_line(self):
        f = self.folders()
        if not f:
            return "standard TV / Movies / Comics / Tutorials folders"
        return "; ".join("%s -> %s" % (n, _friendly(f[k])) for k, n in KINDS if k in f)

    def choose_folders(self, dlg, first=False):
        """Let the person point each kind at a folder they already have."""
        if first and not dlg.yesno(
                self.heading,
                "Do you already have folders for your shows or movies (any name, any drive - e.g. "
                "D:\\My Shows, E:\\Films)?\nKodi Sorter can add new files to them instead of making new "
                "TV / Movies folders. Nothing already in them is moved.",
                nolabel="No, use the standard folders", yeslabel="Yes, pick them"):
            return
        names = dict(KINDS)
        while True:
            have = self.folders()
            opts = ["%s:  %s" % (names[k], _friendly(have[k]) if k in have else "standard folder (" + _STD[k] + ")")
                    for k in self.wanted()]
            opts.append("Done")
            pick = dlg.select("Your library folders - pick one to change", opts)
            if pick < 0 or pick == len(opts) - 1:
                return
            kind = self.wanted()[pick]
            how = dlg.select(names[kind], ["Pick my existing %s folder..." % names[kind].lower(),
                                           "Use the standard folder (%s on the destination drive)" % _STD[kind]])
            folders = self.state.setdefault("folders", {})
            if how == 0:
                path = dlg.browse(0, "Pick the folder that holds your %s" % names[kind].lower(), "files")
                if path:
                    folders[kind] = path
            elif how == 1:
                folders.pop(kind, None)
            self.save()

    def save(self):
        if self.state_file:
            _save(self.state_file, self.state)

    def show_guide(self, dlg):
        md = _read(os.path.join(self.res, "README.md"))
        dlg.textviewer("%s - guide" % self.heading, md_to_kodi(md) if md else
                       "The guide isn't included in this copy. It's on GitHub: akaguyver/kodi-sorter, README.md")

    def show_history(self, dlg):
        md = _read(os.path.join(self.res, "CHANGELOG.md"))
        dlg.textviewer("%s - version history" % self.heading, md_to_kodi(md) if md else "No version history in this copy.")

    def choose_kinds(self, dlg, first=False):
        """Tick-list of what to sort. Returns False if cancelled."""
        now = self.wanted()
        while True:
            picks = dlg.multiselect("What do you want Kodi Sorter to sort? (OK when done)",
                                    [n for _, n in KINDS],
                                    preselect=[i for i, (k, _) in enumerate(KINDS) if k in now])
            if picks is None:
                return False if not first else True  # first run: Back keeps "everything"
            if picks:
                self.state["kinds"] = [KINDS[i][0] for i in picks]
                self.save()
                return True
            dlg.ok(self.heading, "Pick at least one thing to sort.")

    def first_run(self, dlg, returning=False):
        """Welcome screen once. Returns after the person has seen it."""
        if self.state.get("welcomed"):
            return False
        hello = ("Kodi Sorter tidies your downloads into the folders Kodi understands:\n"
                 "TV\\Show\\Season 01, Movies\\Title (Year), Comics\\Series, Tutorials\\Program.\n"
                 "It always shows you the plan first - nothing moves until you say so.")
        if returning:
            hello = "New in this version: a welcome screen, a guide you can read on the TV, and a choice of what to sort.\n" + hello
        dlg.ok("Welcome to %s" % self.heading, hello)
        self.choose_kinds(dlg, first=True)
        self.choose_folders(dlg, first=True)
        if dlg.yesno(self.heading, "Read the guide now? (features and how to get started)\n"
                                   "You can open it any time from the menu: Help.",
                     nolabel="Later", yeslabel="Read it"):
            self.show_guide(dlg)
        self.state["welcomed"] = self.version
        self.state["seen_version"] = self.version
        self.save()
        return True

    def whats_new(self, dlg):
        """After an update: the CHANGELOG lines since the last version seen."""
        old = self.state.get("seen_version")
        if old == self.version:
            return
        self.state["seen_version"] = self.version
        self.save()
        if not old:
            return
        text = changes_since(_read(os.path.join(self.res, "CHANGELOG.md")), old, self.version)
        if text:
            dlg.textviewer("%s - what's new since %s" % (self.heading, old), text)

    def help_menu(self, dlg):
        while True:
            pick = dlg.select("%s - help" % self.heading,
                              ["Read the guide (features, first-time setup)",
                               "Version history (what each update added)",
                               "What to sort (now: %s)" % self.wanted_line(),
                               "My library folders (now: %s)" % self.folders_line(),
                               "Show the welcome screen again"])
            if pick < 0:
                return
            if pick == 0:
                self.show_guide(dlg)
            elif pick == 1:
                self.show_history(dlg)
            elif pick == 2:
                self.choose_kinds(dlg)
            elif pick == 3:
                self.choose_folders(dlg)
            elif pick == 4:
                self.state.pop("welcomed", None)
                self.first_run(dlg)
