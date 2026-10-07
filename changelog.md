# Changelog

## v0.6.2

### Added
  - **Option "Use Dummy GUID Range from Settings"**: checkbox (default: true) to toggle between using the global settings dummy range or entering a custom dummy range directly on the tab.
  - **Option "Replace all GUIDs not in own ranges"**: new checkbox option (default: false) to target all GUIDs outside own ranges.

## v0.6.1

### Added
- **Program Icon**: modern application icon (`AnnoGUIDTool.ico` / `icon.png`) for the application window and compiled Executable.
- **"Replace Dummy GUIDs" Tab Enhancements**:
  - **Checkable GUID Table**: found GUIDs are displayed in a table with checkboxes (`☑` / `☐`) allowing selective replacement.
  - **Selection Controls & Counter**: added `Select All` / `Deselect All` buttons, header column toggle, spacebar shortcut, and selection counter.
  - **Right-Click Context Menu**: right-click on selected rows to select or deselect highlighted GUIDs for replacement.
  - **Option "Use Dummy GUID Range from Settings"**: checkbox (default: true) to toggle between using the global settings dummy range or entering a custom dummy range directly on the tab.
  - **Option "Replace all GUIDs not in own ranges"**: new checkbox option (default: false) to target all GUIDs outside own ranges.

## v0.6.0 (thx to Taludas)

### Added
- **GUID collision warning on import**: a dialog lists GUIDs of a registered mod that
  - the database lists for another mod (the folder above `data/`),
  - the mod defines more than once (two asset definitions, or twice in one `texts_*.xml`; an asset plus its own text entry is fine),
  - are reserved in the Free GUIDs list of another mod project.

  Per GUID you choose:
  - **Migrate**: the mod gets a free GUID. All occurrences in that mod's files are rewritten (definitions, references, comments); other mods stay untouched. Not available for GUIDs defined more than once.
  - **Accept**: the GUID is registered anyway and not reported again. A reservation the other project has not used yet is released.

  Colliding GUIDs are shown in red with "!" in the database table, and the statistics bar counts them. For an accepted collision with another mod, the comment of the mod that had the GUID first is kept.
- **Right-click → "Migrate a mod to a free GUID…"** on a red GUID: choose one of the mods that define it, select its folder or ZIP, and it is moved to the next free GUID (files rewritten, mod registered again).
- **Check Collisions** button: scans a folder of mods (folders and ZIPs) for GUIDs defined in more than one mod, defined twice in one mod, listed for other mods in your database, or reserved in your Free GUIDs lists, without registering anything. The report can be exported as CSV.
- **New tab "Free GUIDs"**: suggests the first continuous block of free GUIDs (number entered by the user) for a mod that is still being written.
  - One list of reserved GUIDs per mod project (drop-down with New / Rename / Delete), so several mods can be worked on at the same time. GUIDs reserved in one list are never suggested for another.
  - Copy GUIDs one by one ("Copy Next Free GUID", double-click, `Ctrl+C`). Copied GUIDs can be marked as used automatically.
  - Mark GUIDs as used with the ☐ box. Used GUIDs are shown struck through.
  - Planning comments: double-click the Comment cell (or `F2`) to type your own comment. On import, the mod's comment replaces it; if the mod has none, the planning comment is taken over into the database.
  - The GUID Database tab shows the reserved, not yet registered GUIDs as blue rows (one per range and project, project name as comment; toggle "Show reserved"). Right-click jumps to the project.
  - "Extend List" reserves more GUIDs directly after the list.
  - After the mod is imported, its GUIDs show as "registered" with their database comment. "Clean Up" removes them and releases unused GUIDs.
  - Reservations are stored per game (`guid_reservations_<game>.json`). Reserved GUIDs are never suggested again and are also skipped by "Replace Dummy GUIDs".
  - A mod dropped onto the window while this tab is shown is registered without leaving the tab.
- **Drag & drop registration** (Windows): drag one or more mod folders or ZIP files from the Explorer onto the window to register their GUIDs in the database of the active game. The tool switches to the GUID Database tab and shows one combined summary. Other dropped files are ignored with a warning. Uses the native Win32 drop mechanism, so no extra package is needed.
- **Drag & drop in "Replace Dummy GUIDs"**: while that tab is shown, a dropped mod folder or ZIP is opened there for replacement instead of being registered (one mod at a time).
- **Sortable table** in the GUID Database tab: click the GUID or Location heading to sort by it, click again to reverse the order. An arrow (▲ / ▼) shows the active sort.

### Changed
- ZIP files without a mod folder above `data/` now use the ZIP file name as mod folder in the stored locations (e.g. `Other/data/base/...` instead of `data/base/...`).


## 0.5.3

### Fixed
- Fixed folder prefix handling in relative file paths so that exactly one directory level above `/data/` is retained (e.g. `[ModName]/data/base/...`), regardless of whether the mod folder itself or a parent directory is selected.


## 0.5.2

### Added
- **Names as comment fallback** when registering a mod. If a GUID has no `GUID - comment` line, its name is used instead:
  1. `<Name>` from the asset's `<Standard>` block (Anno 117 and Anno 1800)
  2. `<Text>` of the entry in a `texts_*.xml` file. Both layouts are supported: text before `<LineId>` (Anno 117) and `<GUID>` before text (Anno 1800).
- **Settings -> General -> Language Comment**: defines which `texts_*.xml` file names are read from (e.g. `german` -> `texts_german.xml`). If the file does not exist or does not contain the GUID, `texts_english.xml` is used, then any other language file. Saved with Enter or when leaving the field.
- Import summary now also shows the number of imported names.

### Changed
- `GUID - comment` lines keep priority. A name is only stored if the GUID has no comment in the database yet, so existing comments are never overwritten.
- New default settings: Appearance Mode `Dark`, Color Theme `dark-blue`, Language `English`, Language Comment `english`. Existing `config.ini` values are kept.
- README updated: top bar, update check, names as fallback, Language Comment, building the EXE and GitHub Actions workflows.
