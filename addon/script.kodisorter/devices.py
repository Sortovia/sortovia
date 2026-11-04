"""Which device Kodi runs on, so Kodi Sorter can give the right instructions
and skip what doesn't work there (an Xbox can't rename files on its drives,
and its file browser can't see them, for example)."""

DEVICES = [
    ("xbox", "Xbox"),
    ("windows", "Windows PC"),
    ("android_tv", "Android TV box / Fire TV / Nvidia Shield"),
    ("android", "Android phone or tablet"),
    ("linux", "Raspberry Pi / LibreELEC / CoreELEC / Linux"),
    ("mac", "Mac"),
    ("apple", "Apple TV / iPhone / iPad"),
    ("webos", "LG TV (webOS)"),
    ("other", "Something else"),
]
NAMES = dict(DEVICES)


def detect(cond, info, log_head="", hostname=""):
    """Best guess from Kodi's own system info. cond = xbmc.getCondVisibility,
    info = xbmc.getInfoLabel. Android can't tell a TV box from a phone: 'android_tv'.
    On an Xbox, Kodi's system info just says Windows; the device model is only in
    the top of Kodi's log ("Running on Microsoft Xbox One S with WINDOWS ..."), so
    log_head (the log's first lines) and the hostname ("XBOXONE") are checked too."""
    import re
    model = re.search(r"Running on (.*?) with ", log_head or "")
    os_info = (info("System.OSVersionInfo") or "").lower()
    if "xbox" in os_info or (model and "xbox" in model.group(1).lower()):
        return "xbox"
    uwp = False
    try:
        uwp = bool(cond("System.Platform.UWP"))
    except Exception:
        pass
    if uwp and "xbox" in (hostname or "").lower():
        return "xbox"
    checks = [("System.Platform.Windows", "windows"), ("System.Platform.UWP", "windows"),
              ("System.Platform.Android", "android_tv"), ("System.Platform.TVOS", "apple"),
              ("System.Platform.IOS", "apple"), ("System.Platform.OSX", "mac"),
              ("System.Platform.WebOS", "webos"), ("System.Platform.Linux", "linux")]
    for c, key in checks:
        try:
            if cond(c):
                return key
        except Exception:
            pass
    return "other"


def can_rename(device):
    """Moving a file on the same drive by renaming it (instant). The Xbox's drives refuse."""
    return device != "xbox"


def add_source_help(device, tutorials="E:\\Tutorials"):
    """How to add a folder (e.g. Tutorials) as a Kodi source on this device."""
    if device == "xbox":
        return ("Adding your folders to Kodi on the Xbox\n\n"
                "The Xbox's Add source browser doesn't list external drives, so type the path:\n"
                "1. Videos > Files > Add videos...\n"
                "2. Select the box that says <None> (not Browse) and type:\n"
                "   win-lib://removable/%s\\\n"
                "3. OK, name it, and for \"This directory contains\" choose:\n"
                "   TV shows for TV, Movies for Movies, None for Tutorials.\n\n"
                "Comics: Pictures already lists your drives (e.g. New Volume (E:)) - open Comics there.\n\n"
                "Never add the whole drive as one source with a content type: it overrides the TV and Movies "
                "folders inside it." % tutorials.replace("\\\\", "\\"))
    return ("Adding your folders to Kodi\n\n"
            "1. Videos > Files > Add videos... > Browse, and pick the folder (e.g. %s).\n"
            "2. OK, name it, and for \"This directory contains\" choose:\n"
            "   TV shows for TV, Movies for Movies, None for Tutorials.\n\n"
            "Comics: Pictures > Add pictures... > Browse > your Comics folder.\n\n"
            "Never add the whole drive as one source with a content type: it overrides the TV and Movies "
            "folders inside it." % tutorials)
