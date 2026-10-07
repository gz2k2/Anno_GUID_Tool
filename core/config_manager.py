"""
config_manager.py
=================

Loading, validating and saving of the user settings stored in ``config.ini``.

The file has one section with general settings and one section PER GAME
holding that game's GUID ranges. Every game can have SEVERAL own ranges and
SEVERAL dummy ranges, stored as comma-separated "start-end" pairs::

    [SETTINGS]
    appearance_mode = Dark          ; "System", "Light" or "Dark"
    color_theme = dark-blue         ; "blue", "green", "dark-blue"
    language = en                   ; "de" or "en"
    auto_assign = false             ; "Automatic" checkbox in the Replace tab
    mark_used_on_copy = true        ; "Mark as used when copied" in the Free GUIDs tab
    show_reserved_in_db = true      ; "Show reserved" in the GUID Database tab
    comment_language = english      ; texts_<language>.xml used for names
    active_game = anno1800          ; game selected in the game selector

    [ANNO1800]
    own_ranges = 1337471142-1337471999, 2144009900-2144009999
    dummy_ranges = 1000000000-1000999999

    [ANNO117]
    ...same keys...

Migration of older config files
-------------------------------
* Single ranges stored as ``own_guid_start`` / ``own_guid_end`` /
  ``dummy_guid_start`` / ``dummy_guid_end`` in a game section are converted
  to a one-entry range list.
* The very first version stored these keys directly in ``[SETTINGS]``; if
  no game section exists yet, they are used for Anno 1800.
The old keys are removed on the next save.

The rest of the application never touches the INI file directly – it only
reads/writes the attributes of :class:`AppConfig` / :class:`GameProfile`
and calls :meth:`AppConfig.save`.
"""

import configparser
import os
import re

from core.constants import (
    CONFIG_FILE,
    DEFAULT_COMMENT_LANGUAGE,
    DEFAULT_DUMMY_RANGE_END,
    DEFAULT_DUMMY_RANGE_START,
    DEFAULT_GAME,
    DEFAULT_GUID_RANGE_END,
    DEFAULT_GUID_RANGE_START,
    GAMES,
)

#: Old single-range keys (pre multi-range versions); removed on save.
_LEGACY_RANGE_KEYS = ("own_guid_start", "own_guid_end", "dummy_guid_start", "dummy_guid_end")

#: One "start-end" pair in the INI value, e.g. "1337471142-1337471999".
_RANGE_ITEM_PATTERN = re.compile(r"(\d+)\s*-\s*(\d+)")


# ======================================================================
# Range helpers (a range is a tuple (start, end), both inclusive)
# ======================================================================
def ranges_overlap(a_start, a_end, b_start, b_end):
    """Return True if the closed intervals [a_start, a_end] and [b_start, b_end] overlap."""
    return a_start <= b_end and b_start <= a_end


def find_overlap(ranges_a, ranges_b=None):
    """Find the first pair of overlapping ranges.

    * ``ranges_b`` given -> compares every range of A with every range of B
      (used for "own ranges vs. dummy ranges").
    * ``ranges_b`` None  -> compares the ranges of A with each other
      (used to reject overlapping rows inside one list).

    :returns: tuple ``(range_x, range_y)`` of the first overlap, or None.
    """
    if ranges_b is None:
        items = sorted(ranges_a)
        for prev, cur in zip(items, items[1:]):
            if ranges_overlap(*prev, *cur):
                return prev, cur
        return None
    for a in ranges_a:
        for b in ranges_b:
            if ranges_overlap(*a, *b):
                return a, b
    return None


def in_ranges(value, ranges):
    """True if the integer ``value`` lies inside at least one range."""
    return any(start <= value <= end for start, end in ranges)


def format_ranges(ranges):
    """Human-readable text of a range list, e.g. ``"100 – 199, 500 – 599"``."""
    return ", ".join(f"{start} – {end}" for start, end in ranges)


def parse_ranges(text):
    """Parse an INI value like ``"100-199, 500-599"`` into ``[(100, 199), (500, 599)]``.

    Invalid pairs (start > end) are dropped. Returns a sorted list.
    """
    result = []
    for start, end in _RANGE_ITEM_PATTERN.findall(text or ""):
        start, end = int(start), int(end)
        if start <= end:
            result.append((start, end))
    return sorted(result)


def serialize_ranges(ranges):
    """Inverse of :func:`parse_ranges`: ``[(100, 199)]`` -> ``"100-199"``."""
    return ", ".join(f"{start}-{end}" for start, end in ranges)


def _read_legacy_range(section, key_start, key_end):
    """Read an old single (start, end) pair; returns ``[(start, end)]`` or None."""
    if key_start not in section and key_end not in section:
        return None
    try:
        start, end = int(section.get(key_start)), int(section.get(key_end))
        return [(start, end)] if start <= end else None
    except (TypeError, ValueError):
        return None


# ======================================================================
# Per-game settings
# ======================================================================
class GameProfile:
    """GUID ranges of ONE game (e.g. Anno 1800).

    :ivar key:          internal game key ("anno1800", "anno117")
    :ivar name:         display name ("Anno 1800")
    :ivar own_ranges:   sorted list of (start, end) – real GUIDs (assigned + registered)
    :ivar dummy_ranges: sorted list of (start, end) – placeholder GUIDs (replaced)
    """

    def __init__(self, key):
        self.key = key
        self.name = GAMES[key]["name"]
        self.section = GAMES[key]["section"]
        self.db_file = GAMES[key]["db_file"]
        self.own_ranges = [(DEFAULT_GUID_RANGE_START, DEFAULT_GUID_RANGE_END)]
        self.dummy_ranges = [(DEFAULT_DUMMY_RANGE_START, DEFAULT_DUMMY_RANGE_END)]

    # ------------------------------------------------------------------
    # INI conversion
    # ------------------------------------------------------------------
    def load_from(self, section):
        """Populate the range lists from an INI section.

        Order of precedence per list: new key (``own_ranges``) -> old single
        range keys (``own_guid_start``/``own_guid_end``) -> default range.
        An empty or completely invalid list also falls back to the default.
        """
        self.own_ranges = (
            parse_ranges(section.get("own_ranges", ""))
            or _read_legacy_range(section, "own_guid_start", "own_guid_end")
            or [(DEFAULT_GUID_RANGE_START, DEFAULT_GUID_RANGE_END)]
        )
        self.dummy_ranges = (
            parse_ranges(section.get("dummy_ranges", ""))
            or _read_legacy_range(section, "dummy_guid_start", "dummy_guid_end")
            or [(DEFAULT_DUMMY_RANGE_START, DEFAULT_DUMMY_RANGE_END)]
        )

    def write_to(self, section):
        """Write the range lists into an INI section and drop old single-range keys."""
        section["own_ranges"] = serialize_ranges(self.own_ranges)
        section["dummy_ranges"] = serialize_ranges(self.dummy_ranges)
        for key in _LEGACY_RANGE_KEYS:
            section.pop(key, None)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    @property
    def first_own_guid(self):
        """Lowest GUID of all own ranges (default start GUID for assignment)."""
        return self.own_ranges[0][0]

    @property
    def own_ranges_text(self):
        """Own ranges as display text, e.g. ``"100 – 199, 500 – 599"``."""
        return format_ranges(self.own_ranges)

    @property
    def dummy_ranges_text(self):
        """Dummy ranges as display text."""
        return format_ranges(self.dummy_ranges)

    def is_own_guid(self, guid_str):
        """True if ``guid_str`` is numeric and inside ANY own range of this game.

        Only these GUIDs are registered in the game's database. Vanilla GUIDs,
        dummy GUIDs and non-numeric placeholders are ignored.
        """
        return guid_str.isdigit() and in_ranges(int(guid_str), self.own_ranges)

    def is_dummy_guid(self, guid_str):
        """True if ``guid_str`` is numeric and inside ANY dummy range of this game.

        Only these GUIDs are replaced with real GUIDs in the "Replace" tab.
        """
        return guid_str.isdigit() and in_ranges(int(guid_str), self.dummy_ranges)

    def next_own_guid(self, value):
        """Smallest GUID >= ``value`` that lies inside an own range, or None.

        Used to continue with the next range when the current one is used up
        (e.g. after the last GUID of range 1 the start of range 2 follows).
        """
        for start, end in self.own_ranges:
            if value <= end:
                return max(value, start)
        return None


# ======================================================================
# Complete config file
# ======================================================================
class AppConfig:
    """In-memory representation of ``config.ini``.

    :ivar games:       dict game key -> :class:`GameProfile`
    :ivar active_game: key of the currently selected game
    """

    SECTION = "SETTINGS"

    def __init__(self, path=CONFIG_FILE):
        self.path = path
        self._parser = configparser.ConfigParser()

        # General defaults – overwritten by load() if the INI contains values.
        self.appearance_mode = "Dark"
        self.color_theme = "dark-blue"
        self.language = "en"
        self.auto_assign = False
        self.replace_non_own = False
        self.use_settings_dummy = True
        #: "Mark as used when copied" checkbox in the Free GUIDs tab
        self.mark_used_on_copy = True
        #: "Show reserved" checkbox in the GUID Database tab
        self.show_reserved_in_db = True
        #: texts_<language>.xml used for names ("Language Comment"), lower case
        self.comment_language = DEFAULT_COMMENT_LANGUAGE
        self.active_game = DEFAULT_GAME
        self.games = {key: GameProfile(key) for key in GAMES}

        self.load()

    @property
    def active(self):
        """:class:`GameProfile` of the currently selected game."""
        return self.games[self.active_game]

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------
    def load(self):
        """Read ``config.ini`` (if present) and populate all attributes.

        Broken values never crash the app; they fall back to their defaults.
        """
        if os.path.exists(self.path):
            try:
                self._parser.read(self.path, encoding="utf-8")
            except Exception as e:  # corrupt file -> keep defaults
                print(f"Error reading config file: {e}")

        if self.SECTION not in self._parser:
            self._parser[self.SECTION] = {}
        s = self._parser[self.SECTION]

        self.appearance_mode = s.get("appearance_mode", self.appearance_mode)
        self.color_theme = s.get("color_theme", self.color_theme)
        self.language = s.get("language", self.language)
        self.auto_assign = s.get("auto_assign", "false").lower() == "true"
        self.replace_non_own = s.get("replace_non_own", "false").lower() == "true"
        self.use_settings_dummy = s.get("use_settings_dummy", "true").lower() == "true"
        self.mark_used_on_copy = s.get("mark_used_on_copy", "true").lower() == "true"
        self.show_reserved_in_db = s.get("show_reserved_in_db", "true").lower() == "true"
        self.comment_language = (
            s.get("comment_language", DEFAULT_COMMENT_LANGUAGE).strip().lower()
            or DEFAULT_COMMENT_LANGUAGE
        )

        active = s.get("active_game", DEFAULT_GAME)
        self.active_game = active if active in GAMES else DEFAULT_GAME

        for key, profile in self.games.items():
            if profile.section in self._parser:
                profile.load_from(self._parser[profile.section])
            elif key == "anno1800":
                # Migration: ranges of the old single-game version were stored
                # in [SETTINGS]; they belonged to the old (Anno 1800) database.
                profile.load_from(s)

        # Old range keys in [SETTINGS] are obsolete (now in game sections).
        for k in _LEGACY_RANGE_KEYS:
            s.pop(k, None)

    def save(self):
        """Write all general settings and every game section to ``config.ini``.

        Other sections/keys that may exist in the file are preserved because
        the same ConfigParser instance that read the file is written back.
        """
        s = self._parser[self.SECTION]
        s["appearance_mode"] = self.appearance_mode
        s["color_theme"] = self.color_theme
        s["language"] = self.language
        s["auto_assign"] = str(bool(self.auto_assign)).lower()
        s["replace_non_own"] = str(bool(self.replace_non_own)).lower()
        s["use_settings_dummy"] = str(bool(self.use_settings_dummy)).lower()
        s["mark_used_on_copy"] = str(bool(self.mark_used_on_copy)).lower()
        s["show_reserved_in_db"] = str(bool(self.show_reserved_in_db)).lower()
        s["comment_language"] = self.comment_language
        s["active_game"] = self.active_game

        for profile in self.games.values():
            if profile.section not in self._parser:
                self._parser[profile.section] = {}
            profile.write_to(self._parser[profile.section])

        with open(self.path, "w", encoding="utf-8") as f:
            self._parser.write(f)
