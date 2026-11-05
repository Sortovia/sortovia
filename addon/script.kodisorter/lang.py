"""The person's language: the audio Sortovia looks for, the subtitles it keeps,
and the language of movie titles from TMDb. English unless they choose another
(or "Kodi's language", the language Kodi's menus are in). Pure, no Kodi imports.
"""
import re

# ISO 639-1 code -> English name, as Sortovia shows it
NAMES = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German", "it": "Italian", "pt": "Portuguese",
    "ru": "Russian", "ja": "Japanese", "zh": "Chinese", "ko": "Korean", "nl": "Dutch", "ar": "Arabic",
    "pl": "Polish", "sv": "Swedish", "fi": "Finnish", "da": "Danish", "no": "Norwegian", "el": "Greek",
    "he": "Hebrew", "hu": "Hungarian", "cs": "Czech", "ro": "Romanian", "vi": "Vietnamese", "id": "Indonesian",
    "uk": "Ukrainian", "bg": "Bulgarian", "hr": "Croatian", "sr": "Serbian", "sl": "Slovenian", "sk": "Slovak",
    "tr": "Turkish", "th": "Thai", "hi": "Hindi", "ms": "Malay", "fa": "Persian", "et": "Estonian",
    "lv": "Latvian", "lt": "Lithuanian", "is": "Icelandic", "ca": "Catalan", "tl": "Filipino", "ta": "Tamil",
    "te": "Telugu", "bn": "Bengali",
}

# 3-letter codes Matroska/MP4 tracks use (both the "bibliographic" and "terminology" forms)
CODES3 = {
    "en": ("eng",), "es": ("spa",), "fr": ("fre", "fra"), "de": ("ger", "deu"), "it": ("ita",), "pt": ("por",),
    "ru": ("rus",), "ja": ("jpn",), "zh": ("chi", "zho"), "ko": ("kor",), "nl": ("dut", "nld"), "ar": ("ara",),
    "pl": ("pol",), "sv": ("swe",), "fi": ("fin",), "da": ("dan",), "no": ("nor", "nob", "nno"), "el": ("gre", "ell"),
    "he": ("heb",), "hu": ("hun",), "cs": ("cze", "ces"), "ro": ("rum", "ron"), "vi": ("vie",), "id": ("ind",),
    "uk": ("ukr",), "bg": ("bul",), "hr": ("hrv",), "sr": ("srp",), "sl": ("slv",), "sk": ("slo", "slk"),
    "tr": ("tur",), "th": ("tha",), "hi": ("hin",), "ms": ("may", "msa"), "fa": ("per", "fas"), "et": ("est",),
    "lv": ("lav",), "lt": ("lit",), "is": ("ice", "isl"), "ca": ("cat",), "tl": ("fil", "tgl"), "ta": ("tam",),
    "te": ("tel",), "bn": ("ben",),
}

# Words that say "this file has that audio" in a release name: "Movie.2020.SPANISH.1080p",
# "Castellano", "VF" (version francaise), "Dublado" (Brazilian dub) ...
FILE_WORDS = {
    "en": ("eng", "english"), "es": ("spa", "spanish", "espanol", "castellano", "latino"),
    "fr": ("fre", "french", "francais", "vf", "vff", "vfq", "truefrench"), "de": ("ger", "german", "deutsch"),
    "it": ("ita", "italian", "italiano"), "pt": ("por", "portuguese", "portugues", "dublado"),
    "ru": ("rus", "russian"), "ja": ("jpn", "japanese"), "ko": ("kor", "korean"), "zh": ("chinese", "mandarin", "cantonese"),
    "nl": ("dutch", "nlsubs"), "pl": ("pol", "polish", "lektor", "dubbing"), "sv": ("swedish", "swe"),
    "fi": ("finnish",), "da": ("danish",), "no": ("norwegian",), "tr": ("turkish", "tur"), "hi": ("hindi",),
    "hu": ("hungarian", "hun"), "cs": ("czech",), "ar": ("arabic",), "he": ("hebrew",), "uk": ("ukrainian", "ukr"),
}


class Language(object):
    def __init__(self, code):
        code = (code or "en").lower()[:2]
        self.code = code if code in NAMES else "en"
        self.name = NAMES[self.code]
        self.codes = set((self.code,) + CODES3.get(self.code, ()))
        words = FILE_WORDS.get(self.code, CODES3.get(self.code, ()) + (self.name.lower(),))
        self.hint_re = re.compile(r"(?<![a-z])(%s)(?![a-z])" % "|".join(re.escape(w) for w in words), re.I)
        self.no_folder = "_No " + self.name     # where files without this audio can be parked
        self.tmdb = "en-US" if self.code == "en" else self.code

    def matches(self, track_lang):
        """Is a track's language tag ("eng", "en", "en-US", "spa") this language?"""
        t = (track_lang or "").lower().split("-")[0]
        return t in self.codes

    def __repr__(self):
        return "Language(%s)" % self.code


def resolve(setting, kodi_code):
    """setting: a code, or "kodi" (or empty) for Kodi's own menu language."""
    if setting and setting != "kodi":
        return Language(setting)
    return Language(kodi_code if (kodi_code or "").lower()[:2] in NAMES else "en")


def choices():
    """(code, name) sorted by name, English first."""
    rest = sorted(((c, n) for c, n in NAMES.items() if c != "en"), key=lambda x: x[1])
    return [("en", "English")] + rest
