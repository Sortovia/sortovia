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


def unwrap(md):
    """Join lines the README wraps for GitHub back into one line per paragraph or list item,
    so Kodi's viewer (which wraps by itself) doesn't break sentences in the middle."""
    out = []
    in_code = False
    for line in md.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            out.append(line)
            continue
        starts_block = (not line.strip() or in_code or re.match(r"^\s*([-*]|\d+\.)\s", line)
                        or re.match(r"^\s*(#|\||-{3,})", line))
        prev = out[-1] if out else ""
        prev_text = (prev.strip() and not prev.strip().startswith(("```", "#", "|"))
                     and not re.match(r"^\s*-{3,}\s*$", prev))
        if not starts_block and prev_text:
            out[-1] = prev.rstrip() + " " + line.strip()
        else:
            out.append(line)
    return "\n".join(out)


def md_to_kodi(md):
    """Markdown -> text for Kodi's text viewer."""
    out = []
    in_code = False
    for line in unwrap(md).splitlines():
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


def sections(md):
    """[(heading, text)] for each "## " part of the guide."""
    out = []
    for part in re.split(r"(?m)^(?=## )", md):
        m = re.match(r"^## (.+)$", part, re.M)
        if m:
            out.append((m.group(1).strip(), re.sub(r"(?m)^-{3,}\s*$", "", part).strip() + "\n"))
    return out


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
    def __init__(self, addon_path, data_path, version, heading, checker=None, std_folder=None, kodi_lang="en",
                 device_guess="other", set_phone=None):
        self.kodi_lang = kodi_lang
        # set_phone(bool): turns using a phone on or off on the settings page
        self.set_phone = set_phone
        self.device_guess = device_guess
        # std_folder(kind) -> "E:\\Movies": where a kind goes by default (None = not known yet)
        self.std_folder = std_folder
        # checker(dlg, kind, folder) -> True when the person wants that folder reorganized
        self.checker = checker
        self.last_reorganize = None
        self.res = os.path.join(addon_path, "resources")
        self.state_file = data_path
        self.version = version
        self.heading = heading
        self.state = _load(data_path) if data_path else {}

    def device(self):
        return self.state.get("device") or self.device_guess

    def device_line(self):
        import devices
        return devices.NAMES.get(self.device(), "?")

    def choose_device(self, dlg):
        """Which device this is: detected, then confirmed from the list."""
        import devices
        guess = self.device()
        keys = [k for k, _ in devices.DEVICES]
        labels = [("%s  (detected)" % n) if k == guess else n for k, n in devices.DEVICES]
        heading = "What is Kodi running on? (so the steps fit your device)"
        try:
            pick = dlg.select(heading, labels, preselect=keys.index(guess) if guess in keys else 0)
        except TypeError:  # older Kodi
            pick = dlg.select(heading, labels)
        if pick >= 0:
            self.state["device"] = keys[pick]
            self.save()

    def wanted(self):
        """Kinds to sort (default: all)."""
        kinds = self.state.get("kinds")
        return [k for k in kinds if k in ALL_KINDS] if kinds else list(ALL_KINDS)

    def wanted_line(self):
        w = self.wanted()
        return "everything" if len(w) == len(ALL_KINDS) else ", ".join(n for k, n in KINDS if k in w)

    def language(self):
        import lang
        return lang.resolve(self.state.get("language", "en"), self.kodi_lang)

    def language_line(self):
        l = self.language()
        return ("%s (Kodi's language)" % l.name) if self.state.get("language") == "kodi" else l.name

    def choose_language(self, dlg):
        """Your language: the audio to look for, subtitles to keep, movie titles from TMDb."""
        import lang
        kodi = lang.resolve("kodi", self.kodi_lang)
        opts = [("kodi", "Use Kodi's language (%s)" % kodi.name)] + lang.choices()
        now = self.state.get("language", "en")
        labels = [("%s  (now)" % n) if c == now else n for c, n in opts]
        pick = dlg.select("Your language - Sortovia keeps videos with audio in it, keeps its subtitles "
                          "and names movies in it", labels)
        if pick >= 0:
            self.state["language"] = opts[pick][0]
            self.save()
        return pick >= 0

    def _std_line(self, kind, short=False):
        """"standard folder: E:\\Movies", or where it will be when the drive isn't known yet."""
        where = None
        try:
            where = self.std_folder(kind) if self.std_folder else None
        except Exception:
            where = None
        if where:
            return where if short else "standard folder: %s" % where
        text = "%s on the drive you sort to (you pick it when you sort)" % _STD[kind]
        return text if short else "standard folder: " + text

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
                "D:\\My Shows, E:\\Films)?\nSortovia can add new files to them instead of making new "
                "TV / Movies folders. Nothing already in them is moved.",
                nolabel="No, use the standard folders", yeslabel="Yes, pick them"):
            return
        names = dict(KINDS)
        while True:
            have = self.folders()
            opts = ["%s:  %s" % (names[k], _friendly(have[k]) if k in have else self._std_line(k))
                    for k in self.wanted()]
            opts.append("Done")
            pick = dlg.select("Your library folders - pick one to change", opts)
            if pick < 0 or pick == len(opts) - 1:
                return
            kind = self.wanted()[pick]
            how = dlg.select(names[kind], ["Pick my existing %s folder..." % names[kind].lower(),
                                           "Use the standard folder: %s" % self._std_line(kind, short=True)])
            folders = self.state.setdefault("folders", {})
            if how == 0:
                path = dlg.browse(0, "Your %s folder" % names[kind].lower(), "files")
                if path:
                    folders[kind] = path
                    self.save()
                    if self.checker and self.checker(dlg, kind, path):
                        self.state["reorganize"] = [kind, path]  # done after the welcome / help screens
                        self.save()
                        return
            elif how == 1:
                folders.pop(kind, None)
            self.save()

    def pop_reorganize(self):
        """A folder the person asked to reorganize: sets last_reorganize, returns True once."""
        r = self.state.pop("reorganize", None)
        if not r:
            return False
        self.save()
        self.last_reorganize = tuple(r)
        return True

    def save(self):
        if self.state_file:
            _save(self.state_file, self.state)

    def show_guide(self, dlg, pick=False, topic=None):
        """The whole guide, one topic (a word in its heading), or a list of topics to choose from."""
        md = _read(os.path.join(self.res, "README.md"))
        if not md:
            dlg.textviewer("%s - guide" % self.heading, "The guide isn't included in this copy. Reinstall Sortovia to get it.")
            return
        parts = sections(md)
        if topic:
            for title, body in parts:
                if topic in title.lower():
                    dlg.textviewer(title, md_to_kodi(body))
                    return
        while pick:
            choice = dlg.select("%s - guide" % self.heading, ["The whole guide"] + [t for t, _ in parts])
            if choice < 0:
                return
            if choice == 0:
                dlg.textviewer("%s - guide" % self.heading, md_to_kodi(md))
            else:
                dlg.textviewer(parts[choice - 1][0], md_to_kodi(parts[choice - 1][1]))
        dlg.textviewer("%s - guide" % self.heading, md_to_kodi(md))

    def show_history(self, dlg):
        md = _read(os.path.join(self.res, "CHANGELOG.md"))
        dlg.textviewer("%s - version history" % self.heading, md_to_kodi(md) if md else "No version history in this copy.")

    def choose_kinds(self, dlg, first=False):
        """Tick-list of what to sort. Returns False if cancelled."""
        now = self.wanted()
        while True:
            picks = dlg.multiselect("What do you want Sortovia to sort? (OK when done)",
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
        hello = ("Sortovia tidies your downloads into the folders Kodi understands:\n\n"
                 "    TV\\Show\\Season 01\n    Movies\\Title (Year)\n    Comics\\Series\n    Tutorials\\Program\n\n"
                 "It always shows you the plan first, and nothing moves until you say so.\n\n"
                 "Sortovia began as a tool for Kodi on an Xbox, with a phone as the hotspot. It's now capable of much more: "
                 "it's built for Kodi on other devices too, and adds comic tools, library backups, Real-Debrid downloads "
                 "and importing files from your phone.\n\nEvery step is in the guide, under Help & settings.")
        if returning:
            hello = "New in this version: a welcome screen, a guide you can read on the TV, and a choice of what to sort.\n" + hello
        dlg.ok("Welcome to %s" % self.heading, hello)
        self.choose_device(dlg)
        self.choose_kinds(dlg, first=True)
        self.choose_language(dlg)
        self.choose_folders(dlg, first=True)
        if self.set_phone:
            phone = dlg.yesno(self.heading,
                              "Do you want to use a phone as a download source? It's optional.\n\n"
                              "Sortovia can import files directly from your phone over a Wi-Fi connection. For now, "
                              "YouTube downloads go through a phone too.\n\n"
                              "Choosing No hides those options. You can change this in Help & settings > Settings.",
                              nolabel="No", yeslabel="Yes")
            self.set_phone(bool(phone))
            if phone:
                dlg.ok(self.heading, "Set the phone up when you're ready. The steps for Android and iPhone are under "
                                     "Help & settings > How to set up your phone.")
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
                               "Your language (now: %s)" % self.language_line(),
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
                self.choose_language(dlg)
            elif pick == 5:
                self.state.pop("welcomed", None)
                self.first_run(dlg)
