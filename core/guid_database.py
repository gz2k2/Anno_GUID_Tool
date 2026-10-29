"""
guid_database.py
================

Persistent store of all GUIDs that are already used by the user's mods.

Every supported game (see ``GAMES`` in constants.py) has its OWN database
file, e.g. ``guid_database_anno1800.json`` and ``guid_database_anno117.json``.
One :class:`GuidDatabase` instance is created per game.

The database is a JSON file mapping each GUID (as string) to an entry with
the mod-relative XML files it was found in and an optional comment::

    {
        "2144009900": {
            "comment": "Praefectus Specialists Name",
            "locations": ["data/config/gui/texts_*.xml"]
        },
        "1337471142": {
            "comment": "",
            "locations": ["data/config/export/main/asset/assets.xml"]
        }
    }

GUID collisions
---------------
A GUID whose locations belong to MORE THAN ONE mod (the folder above
``data/``, see :func:`mod_of_location`) is a collision – e.g. two alternative
versions of a mod that reuse the same GUID. When the user accepts such a
collision during an import, the mods involved are stored, so the same
collision is not reported again (a third mod would be)::

    "2144009900": {
        "comment": "...",
        "locations": ["[Mod] v1/data/...", "[Mod] v2/data/..."],
        "accepted_mods": ["[Mod] v1", "[Mod] v2"]
    }

Two more kinds of collision are stored as lists in the entry:

* ``duplicate_in`` – mods that define the GUID more than once themselves
  (two asset definitions, or twice in one texts_*.xml file). Updated on
  every import of the mod, so it disappears once the mod is fixed.
* ``reserved_in`` – "Free GUIDs" lists (other mod projects) in which the
  GUID was still reserved when the user accepted the import. Shown as a
  collision only while the GUID is still reserved there.

``accepted_mods``, ``duplicate_in`` and ``reserved_in`` are only written for
GUIDs that have them.

Older database files stored only the location list per GUID
(``"1337471142": ["assets.xml"]``). They are converted to the new format
automatically when loaded and written in the new format on the next save.

It serves two purposes:

1. Overview / search of all used GUIDs (tab "GUID Database").
2. Collision avoidance: when real GUIDs are assigned to dummies or a free
   block is suggested, every GUID that already exists in the database is
   skipped. GUIDs that are only reserved (tab "Free GUIDs", see
   guid_reservations.py) are passed in as ``extra_taken`` and skipped too.
"""

import bisect
import json
import os
import shutil

from core.constants import GAMES, LEGACY_DB_FILE
from core.xml_scanner import mod_of_location


def guid_sort_key(guid):
    """Sort key that orders numeric GUIDs numerically, others alphabetically.

    Returns a tuple so numbers and strings never get compared directly
    (which would raise a TypeError in Python 3). Numeric GUIDs come first.
    """
    return (0, int(guid), "") if guid.isdigit() else (1, 0, guid)


#: Optional list fields of an entry (see "GUID collisions" above).
_LIST_FIELDS = ("accepted_mods", "duplicate_in", "reserved_in")


def _new_entry(locations=None, comment=""):
    """Create a database entry dict in the current format."""
    return {"comment": comment or "", "locations": list(locations or [])}


def _normalize_entry(value):
    """Convert an entry read from JSON into the current dict format.

    * old format: ``["a.xml", "b.xml"]``            -> ``{"comment": "", "locations": [...]}``
    * new format: ``{"comment": ..., "locations": ...}`` -> missing keys are added
    * anything else (corrupt data)                   -> empty entry
    """
    if isinstance(value, list):
        return _new_entry(value)
    if isinstance(value, dict):
        entry = _new_entry(value.get("locations", []), value.get("comment", ""))
        for key in _LIST_FIELDS:
            items = value.get(key)
            if isinstance(items, list) and items:
                entry[key] = sorted(str(item) for item in items)
        return entry
    return _new_entry()


class GuidDatabase:
    """Wrapper around the JSON GUID database with convenience methods."""

    def __init__(self, path):
        """:param path: JSON file of one game (e.g. ``guid_database_anno1800.json``)."""
        self.path = path
        #: dict[str, dict] – GUID -> {"comment": str, "locations": list[str]}
        self.entries = self._load()

    # ------------------------------------------------------------------
    # Python protocol helpers (allow "guid in db" and "len(db)")
    # ------------------------------------------------------------------
    def __contains__(self, guid):
        return guid in self.entries

    def __len__(self):
        return len(self.entries)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self):
        """Load the JSON file (any format version). Returns {} if missing or unreadable."""
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {str(guid): _normalize_entry(value) for guid, value in raw.items()}
        except Exception as e:
            print(f"Error loading GUID database: {e}")
            return {}

    def save(self):
        """Write the database to disk (pretty-printed, UTF-8, non-ASCII kept)."""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, indent=4, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Modification
    # ------------------------------------------------------------------
    def add_guid(self, guid, comment=""):
        """Create a GUID database entry without inventing a file location.

        Existing entries are left unchanged. This is used when a reserved
        Free GUID is converted into a Mod Package before it occurs in a mod file.
        """
        guid = str(guid)
        if guid in self.entries:
            return False
        self.entries[guid] = _new_entry([], comment.strip())
        return True

    def add_location(self, guid, location):
        """Register ``guid`` as used in ``location``.

        * New GUID       -> created with ``[location]`` and empty comment; returns True.
        * Existing GUID  -> ``location`` appended if not yet listed; returns False.

        The return value lets callers count how many *new* GUIDs were added.
        """
        if guid not in self.entries:
            self.entries[guid] = _new_entry([location])
            return True
        locations = self.entries[guid]["locations"]
        if location not in locations:
            locations.append(location)
        return False

    def set_comment(self, guid, comment):
        """Set the comment of an EXISTING GUID (unknown GUIDs are ignored).

        :returns: True if the stored comment actually changed.
        """
        entry = self.entries.get(guid)
        if entry is None or entry["comment"] == comment:
            return False
        entry["comment"] = comment
        return True

    def set_comment_if_empty(self, guid, comment):
        """Set the comment of an EXISTING GUID only if it has no comment yet.

        Used for fallback names (<Name> / texts) so they never overwrite a
        comment that was stored before (e.g. from a "GUID - comment" line).

        :returns: True if the comment was set.
        """
        entry = self.entries.get(guid)
        if entry is None or entry["comment"] or not comment:
            return False
        entry["comment"] = comment
        return True

    def move_to(self, guids, target):
        """Move ``guids`` (with locations and comment) into the database ``target``.

        * GUID not yet in ``target`` -> copied completely.
        * GUID already in ``target`` -> location lists are merged (no duplicates);
          the target's comment is kept, the source comment is only used if the
          target has none. So no information of either database is lost.
        * Afterwards the GUIDs are removed from THIS database.

        Unknown GUIDs are ignored. Neither database is saved here – the caller
        must call :meth:`save` on both.

        :returns: tuple ``(moved, merged)`` – number of GUIDs newly created in
                  ``target`` and number of GUIDs merged into existing entries.
        """
        moved = merged = 0
        for guid in guids:
            entry = self.entries.pop(guid, None)
            if entry is None:
                continue
            if guid in target.entries:
                merged += 1
            else:
                moved += 1
            for location in entry["locations"]:
                target.add_location(guid, location)
            if entry["comment"] and not target.entries[guid]["comment"]:
                target.entries[guid]["comment"] = entry["comment"]
            for key in _LIST_FIELDS:
                if entry.get(key):
                    target._update_list(guid, key, add=entry[key])
        return moved, merged

    def _update_list(self, guid, key, add=(), remove=()):
        """Add / remove items of the list field ``key``; drop the field when empty."""
        entry = self.entries.get(guid)
        if entry is None:
            return
        items = (set(entry.get(key, [])) | set(add)) - set(remove)
        if items:
            entry[key] = sorted(items)
        else:
            entry.pop(key, None)

    def accept_collision(self, guid, mods):
        """Remember that the collision of ``guid`` between ``mods`` is accepted.

        Merged with mods accepted earlier. Unknown GUIDs are ignored.
        """
        self._update_list(guid, "accepted_mods", add=mods)

    def set_duplicate(self, guid, mod, duplicate):
        """Record whether ``mod`` defines ``guid`` more than once (``duplicate_in``)."""
        if duplicate:
            self._update_list(guid, "duplicate_in", add=[mod])
        else:
            self._update_list(guid, "duplicate_in", remove=[mod])

    def add_reserved_conflict(self, guid, list_name):
        """Record that ``guid`` was imported while reserved in the Free GUIDs list ``list_name``."""
        self._update_list(guid, "reserved_in", add=[list_name])

    def remove_mod(self, guid, mod):
        """Remove all locations of ``mod`` from ``guid`` (used after migrating the mod).

        The mod is also removed from ``accepted_mods`` / ``duplicate_in``. If no
        location is left, the whole entry is deleted.
        """
        entry = self.entries.get(guid)
        if entry is None:
            return
        entry["locations"] = [loc for loc in entry["locations"] if mod_of_location(loc) != mod]
        if not entry["locations"]:
            del self.entries[guid]
            return
        self._update_list(guid, "accepted_mods", remove=[mod])
        if len(entry.get("accepted_mods", [])) < 2:   # nothing left to collide with
            entry.pop("accepted_mods", None)
        self._update_list(guid, "duplicate_in", remove=[mod])

    def delete(self, guids):
        """Remove all given GUIDs from the database (unknown GUIDs are ignored)."""
        for guid in guids:
            self.entries.pop(guid, None)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def sorted_items(self):
        """Return ``[(guid, comment, [locations...]), ...]`` sorted by GUID (numeric first)."""
        return [
            (g, self.entries[g]["comment"], self.entries[g]["locations"])
            for g in sorted(self.entries, key=guid_sort_key)
        ]

    def mods_of(self, guid):
        """Set of mods (folder above ``data/``) whose files define ``guid``.

        Locations without a known mod folder are left out.
        """
        entry = self.entries.get(guid)
        if entry is None:
            return set()
        return {m for m in map(mod_of_location, entry["locations"]) if m}

    def is_collision(self, guid, reservations=None):
        """True if ``guid`` is a collision.

        * defined in more than one mod, or
        * defined more than once inside one mod (``duplicate_in``), or
        * still reserved in a Free GUIDs list it was imported against
          (``reserved_in``; only checked if ``reservations`` is given).
        """
        entry = self.entries.get(guid)
        if entry is None:
            return False
        if len(self.mods_of(guid)) > 1 or entry.get("duplicate_in"):
            return True
        if reservations is not None:
            return any(guid in reservations.lists.get(name, {}) for name in entry.get("reserved_in", []))
        return False

    def accepted_mods(self, guid):
        """Set of mods whose collision on ``guid`` was accepted by the user."""
        return set(self.entries.get(guid, {}).get("accepted_mods", []))

    def duplicate_in(self, guid):
        """Set of mods recorded as defining ``guid`` more than once."""
        return set(self.entries.get(guid, {}).get("duplicate_in", []))

    def _taken_numbers(self, extra_taken=()):
        """Sorted list of all numeric GUIDs in the database plus ``extra_taken``."""
        guids = set(self.entries) | set(extra_taken)
        return sorted(int(g) for g in guids if g.isdigit())

    def count_free(self, ranges, from_guid, extra_taken=()):
        """Number of unregistered GUIDs inside ``ranges`` that are >= ``from_guid``.

        :param ranges:      sorted list of (start, end) tuples (own ranges of a game)
        :param from_guid:   only GUIDs from this value upwards are counted
        :param extra_taken: further GUIDs (strings) that count as used,
                            e.g. reserved GUIDs

        Computed per range as "size minus used GUIDs", so it is fast even for
        huge ranges (no iteration over the ranges themselves).
        """
        used = self._taken_numbers(extra_taken)
        free = 0
        for start, end in ranges:
            start = max(start, from_guid)
            if start > end:
                continue
            free += (end - start + 1) - sum(1 for g in used if start <= g <= end)
        return free

    def allocate(self, count, ranges, from_guid, extra_taken=()):
        """Return ``count`` free GUIDs (as strings), ascending from ``from_guid``.

        The ranges are walked in ascending order; when one range is used up,
        allocation continues at the start of the next one. GUIDs already in
        the database or in ``extra_taken`` are skipped, so gaps are filled
        first. The caller must ensure enough free GUIDs exist (see
        :meth:`count_free`).
        """
        taken = set(self.entries) | set(extra_taken)
        result = []
        for start, end in ranges:
            current = max(start, from_guid)
            while current <= end and len(result) < count:
                if str(current) not in taken:
                    result.append(str(current))
                current += 1
            if len(result) >= count:
                break
        return result

    def find_free_block(self, count, ranges, from_guid, extra_taken=()):
        """Return the first CONTINUOUS block of ``count`` free GUIDs, or None.

        Unlike :meth:`allocate`, the GUIDs have no gaps: the block is the
        lowest run of ``count`` consecutive GUIDs >= ``from_guid`` that lies
        completely inside ONE own range and contains no GUID of the database
        or of ``extra_taken``.

        Only the gaps between taken GUIDs are inspected, so this is fast even
        for huge ranges.

        :return: list of ``count`` GUID strings, or None if no block fits
        """
        taken = self._taken_numbers(extra_taken)
        for start, end in ranges:
            current = max(start, from_guid)
            index = bisect.bisect_left(taken, current)
            while current <= end:
                # Next taken GUID inside this range (or "end + 1" if none).
                blocker = taken[index] if index < len(taken) and taken[index] <= end else end + 1
                if blocker - current >= count:
                    return [str(g) for g in range(current, current + count)]
                current = blocker + 1
                index += 1
        return None


def migrate_legacy_database(target_game):
    """Move the old single ``guid_database.json`` into the database of ``target_game``.

    Older versions of the tool only knew ONE database. On the first start of
    the multi-game version this file is copied to the database file of
    ``target_game`` (Anno 1800 by default) and the old file is renamed to
    ``guid_database.json.bak`` so the migration runs only once.

    Nothing happens if there is no legacy file or if the target database
    already exists (an existing database is never overwritten).

    :returns: True if a migration was performed, otherwise False.
    """
    target = GAMES[target_game]["db_file"]
    if not os.path.exists(LEGACY_DB_FILE) or os.path.exists(target):
        return False
    try:
        shutil.copy2(LEGACY_DB_FILE, target)
        os.replace(LEGACY_DB_FILE, LEGACY_DB_FILE + ".bak")
        return True
    except Exception as e:
        print(f"Error migrating legacy database: {e}")
        return False
