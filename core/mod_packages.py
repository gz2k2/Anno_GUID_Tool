"""Persistent named GUID range packages, stored separately for each game."""
from __future__ import annotations

import json
import os
from typing import Iterable


class ModPackages:
    """Manage named packages, each containing one or more inclusive GUID ranges."""

    def __init__(self, path: str):
        self.path = path
        self.packages: dict[str, list[tuple[int, int]]] = {}
        self.active: str | None = None
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            source = raw.get("packages", raw) if isinstance(raw, dict) else {}
            for name, ranges in source.items():
                clean = []
                if isinstance(ranges, list):
                    for item in ranges:
                        if isinstance(item, (list, tuple)) and len(item) == 2:
                            start, end = int(item[0]), int(item[1])
                            if 0 <= start <= end:
                                clean.append((start, end))
                self.packages[str(name)] = sorted(set(clean))
            active = raw.get("active") if isinstance(raw, dict) else None
            self.active = active if active in self.packages else next(iter(self.packages), None)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            print(f"Error loading mod packages: {exc}")

    def save(self) -> None:
        data = {"active": self.active,
                "packages": {name: [[start, end] for start, end in ranges]
                             for name, ranges in self.packages.items()}}
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)

    def names(self) -> list[str]:
        return sorted(self.packages, key=str.casefold)

    def add(self, name: str) -> bool:
        name = name.strip()
        if not name or name in self.packages:
            return False
        self.packages[name] = []
        self.active = name
        return True

    def rename(self, old: str, new: str) -> bool:
        new = new.strip()
        if old not in self.packages or not new or (new != old and new in self.packages):
            return False
        self.packages[new] = self.packages.pop(old)
        if self.active == old:
            self.active = new
        return True

    def delete(self, name: str) -> bool:
        if name not in self.packages:
            return False
        del self.packages[name]
        self.active = next(iter(self.packages), None)
        return True

    def overlapping_package(self, start: int, end: int, ignore=None) -> str | None:
        """Return the first overlapping package, excluding one range while editing."""
        for name, ranges in self.packages.items():
            for index, (other_start, other_end) in enumerate(ranges):
                if ignore == (name, index):
                    continue
                if start <= other_end and other_start <= end:
                    return name
        return None

    def add_range(self, name: str, start: int, end: int) -> bool:
        if name not in self.packages or start < 0 or end < start:
            return False
        if self.overlapping_package(start, end) is not None:
            return False
        self.packages[name].append((start, end))
        self.packages[name].sort()
        return True

    def add_guids(self, name: str, guids: Iterable[str]) -> tuple[int, str | None]:
        """Add numeric GUIDs to a package and compact adjacent values into ranges.

        GUIDs already covered by this package are ignored. If a GUID belongs
        to another package, nothing is changed and that package name is returned.
        """
        if name not in self.packages:
            return 0, None
        numbers = sorted({int(guid) for guid in guids if str(guid).isdigit()})
        own_ranges = self.packages[name]
        new_numbers = []
        for number in numbers:
            if any(start <= number <= end for start, end in own_ranges):
                continue
            conflict = self.overlapping_package(number, number)
            if conflict is not None and conflict != name:
                return 0, conflict
            new_numbers.append(number)
        if not new_numbers:
            return 0, None

        all_ranges = list(own_ranges) + [(number, number) for number in new_numbers]
        all_ranges.sort()
        merged = []
        for start, end in all_ranges:
            if merged and start <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        self.packages[name] = merged
        return len(new_numbers), None

    def update_range(self, name: str, index: int, start: int, end: int) -> tuple[bool, str | None]:
        """Replace one range and keep package ranges sorted.

        Returns ``(changed, conflict_package)``. The existing range is ignored
        during overlap validation so it can be resized in place. No data is
        changed when the package/index is invalid or another range overlaps.
        """
        ranges = self.packages.get(name)
        if ranges is None or not 0 <= index < len(ranges) or start < 0 or end < start:
            return False, None
        conflict = self.overlapping_package(start, end, ignore=(name, index))
        if conflict is not None:
            return False, conflict
        new_range = (start, end)
        if ranges[index] == new_range:
            return False, None
        ranges[index] = new_range
        ranges.sort()
        return True, None

    def remove_range(self, name: str, index: int) -> bool:
        ranges = self.packages.get(name)
        if ranges is None or not 0 <= index < len(ranges):
            return False
        ranges.pop(index)
        return True

    def matching_ranges(self, guids: Iterable[str]):
        """Yield package/range/matching GUIDs for ranges containing database GUIDs."""
        numeric = sorted((int(guid), guid) for guid in guids if str(guid).isdigit())
        for name in self.names():
            for start, end in self.packages[name]:
                matches = [guid for number, guid in numeric if start <= number <= end]
                if matches:
                    yield name, start, end, matches
