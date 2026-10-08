# Anno GUID Tool

### Support

---

*Support the project:*
<a href="https://ko-fi.com/gz2k2" target="_blank">Buy Me A Coffee</a>

---

**[English](#english) | [Deutsch](#deutsch)**

---

<a name="english"></a>

## English

A desktop tool for **Anno 117** and **Anno 1800** modders. It keeps track of the GUIDs your mods use and replaces temporary dummy GUIDs with real, unused GUIDs from your own GUID ranges.

### Features

- **Two games, two databases.** Anno 117 and Anno 1800 each have their own GUID database and their own GUID ranges. Choose the game in the selector above the tabs.
- **GUID database.**
  - Register mods from a folder or a ZIP archive, or drag them onto the window (Windows).
  - Search by GUID, comment or file path.
  - Sort by GUID or location, ascending or descending.
  - Export to CSV.
  - Delete entries.
  - Move entries to the other game.
- **Comments.** Comments in the format `GUID - text` inside XML comments are read when a mod is registered and shown in their own column.
- **Free GUID blocks.** Get a continuous block of free GUIDs for a mod you are still writing. The GUIDs stay reserved until the mod is imported.
- **Dummy GUID replacement.** Dummy GUIDs in a mod are replaced with free GUIDs from your own ranges. Definitions and all references are updated.
- **Multiple GUID ranges per game.** You can define any number of own ranges and dummy ranges for each game.
- **Collision protection.** GUIDs that are already registered or reserved are never assigned again.
- **Collision check.** Warns when a mod you register reuses a GUID of another mod, defines a GUID twice, or uses a GUID reserved for another project: migrate it to a free GUID, or accept it and keep it marked. A folder of mods can also be checked without registering anything.
- **German and English UI.** Light, dark and system themes are available.

### Requirements

- Python 3 with Tkinter (included in the standard Windows installer)
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)

```bash
pip install customtkinter
```

### Getting started

```bash
python main.py
```

On first start:

1. Open **Settings → Anno 117 / Anno 1800** and enter your own GUID ranges and dummy GUID ranges.
2. Select the game in the game selector at the top.
3. Register your existing mods in the **GUID Database** tab so their GUIDs are known and never assigned again.

### Usage

#### Tab "GUID Database"

| Action | How |
|---|---|
| Register a mod | **Register Folder in DB** or **Register ZIP in DB** |
| Register by drag & drop | Drag one or more mod folders / ZIP files from the Explorer onto the window (Windows only). The tool switches to this tab and shows one summary for all dropped mods. Other files are ignored. Works on every tab except **Replace Dummy GUIDs** (there a drop opens the mod instead). |
| Search | Type in the search field. It filters by GUID, comment and location. |
| Show reserved GUIDs | **Show reserved** shows the GUIDs reserved in the **Free GUIDs** lists that are not registered yet: one blue row per continuous range and project, with the project name as comment. Right-click → **Show in Free GUIDs** opens the project. Delete and Move ignore these rows. |
| Copy GUIDs | Right-click one or more selected entries → **Copy GUID**. Selected GUIDs are copied one per line. |
| Sort | Click the **GUID** or **Location** column heading. Click again to reverse the order (▲ ascending, ▼ descending). |
| Export | **Export .csv** writes `GUID;Comment;Location`, separated by `;` (UTF-8) |
| Delete | Button, `Del` key or right-click menu |
| Select all | `Ctrl+A` |
| Move to other game | Right-click → **Move to Anno 117 / Anno 1800** |
| Migrate a colliding GUID | Right-click a red GUID → **Migrate a mod to a free GUID…** |
| Check for GUID collisions | **Check Collisions**, then choose a folder with mods. Nothing is registered. |
| Scroll horizontally | Scroll bar or `Shift` + mouse wheel |

When a mod is registered:

- Only GUIDs defined in `<GUID>` or `<LineId>` tags are registered.
- They must lie inside one of the **own GUID ranges** of the active game.
- Language files (`texts_english.xml`, `texts_german.xml`, …) are grouped as `texts_*.xml`.

**Comments.** The comment column is filled from XML comments that contain one `GUID - text` entry per line:

```xml
<!--
2144009900 - Praefectus Specialists Name
2144009901 - Praefectus Specialists Description
-->
<!-- 2144009902 - Praefectus Adriana Name -->
```

- A comment may be in any XML file of the same mod.
- Normal hyphens, dashes (`–`, `—`) and non-breaking spaces are accepted as separators.
- A comment found during registration overwrites the stored one. GUIDs without a comment in the mod keep their stored comment.
- After the import, a summary shows how many comments were found, changed, unchanged or skipped, and how many names were imported.

**Names as fallback.** If a GUID has no `GUID - text` comment, its name is used instead:

1. `<Name>` from the asset's `<Standard>` block (Anno 117 and Anno 1800)
2. `<Text>` of the entry in a `texts_*.xml` file. Both layouts are supported: text before `<LineId>` (Anno 117) and `<GUID>` before text (Anno 1800). The language file is set in **Settings → General → Language Comment** (e.g. `german` → `texts_german.xml`). If that file does not exist or does not contain the GUID, `texts_english.xml` is used, then any other language.

A name is only stored if the GUID has no comment in the database yet, so it never overwrites an existing comment.

**Moving entries.** Comments and file locations are moved together with the GUID. If the GUID already exists in the target database, the location lists are merged.

**GUID collisions.** The mod of a file is the folder directly above `data/`, e.g. `[Specialists] v2/data/...`. For a ZIP without such a folder, the ZIP file name is used. When you register a mod, three kinds of collision are detected:

- **Defined in another mod:** the database already lists the GUID for a different mod.
- **Defined more than once in the mod:** the GUID has two asset definitions (`<Standard>` blocks, in the same or different files), or two entries in the same `texts_*.xml` file. An asset and its own text entry share the GUID by design, so that is not a collision. Commented-out XML is ignored.
- **Reserved in another project:** the GUID is reserved in the **Free GUIDs** list of a different mod project. The mod's own project is the list selected in the **Free GUIDs** tab, if it holds any of the mod's GUIDs. Otherwise it is the list that holds most of them. The dialog names the list it assumed.

A dialog lists the colliding GUIDs with all their problems. For each one you choose:

- **Migrate:** the registered mod gets the proposed free GUID. Every occurrence of the old GUID in that mod's files is replaced, including definitions, references and `GUID - text` comments. Other mods are not changed. You confirm this first, because it cannot be undone. This is not available for GUIDs that are defined more than once: the tool cannot tell which definition should change, so fix those in the mod.
- **Accept:** the GUID is registered anyway. Use this for alternative versions of a mod that are never loaded together. Accepted collisions are not reported again. For a reservation in another project: if that project has not used the GUID yet, its reservation is released. If it has, the GUID stays marked while it is reserved there.

Every GUID starts on **Accept**. **Set to Migrate** and **Set to Accept** only change the decision of the selected rows, or of all rows if none is selected. The status line below the table shows the current decisions. Click **Continue Import** to apply them and register the mod. **Cancel Import** skips this mod. The summary lists every migrated GUID as `old → new`.

Colliding GUIDs are shown **in red with `!`** in the table, and the statistics bar shows how many there are. A duplicate inside a mod loses its mark when you register the fixed mod again.

**Migrating later.** Right-click a red GUID → **Migrate a mod to a free GUID…**. The dialog lists the mods that define the GUID, with the last registered one selected, and shows the proposed free GUID. The database only stores relative paths, so you then select the folder or ZIP of the chosen mod. After you confirm, the GUID is replaced in that mod's files only, the mod's old locations are removed from the GUID, and the mod is registered again. Mods that define the GUID more than once themselves cannot be migrated.

When you accept a collision with another mod, the comment of the mod that had the GUID first is kept.

**Check Collisions.** Scans a folder with many mods, both folders and ZIP files at any depth, without registering anything. It checks every numeric GUID, not only your own ranges, so you can also check other modders' work. The report lists:

- GUIDs that are defined in more than one of the scanned mods
- GUIDs that one scanned mod defines more than once
- GUIDs of the scanned mods that your database lists for other mods
- GUIDs of the scanned mods that are reserved in your **Free GUIDs** lists

The report can be exported as CSV.

#### Tab "Free GUIDs"

Use this tab while you are still writing a mod and need real GUIDs right away.

**Mod projects.** Reserved GUIDs are kept in one list per mod project. Choose the list in **Mod project**, or create, rename and delete lists with **New**, **Rename** and **Delete**. Everything below works on the selected list. If there is no list yet, the first **Suggest Free Block** creates one ("My Mod"). Deleting a list releases its GUIDs.

1. Enter the **Number of GUIDs** and click **Suggest Free Block**. The tool reserves the first continuous block of free GUIDs in your own ranges. GUIDs that are registered or already reserved are skipped.
2. Copy the GUIDs into your mod one at a time:
   - **Copy Next Free GUID** copies the lowest free GUID of the list.
   - Double-click a row (outside the **Comment** cell), or select rows and press `Ctrl+C`.
   - With **Mark as used when copied** (on by default), a copied GUID is marked as used right away.
3. Click the **☐** box of a row to mark it as used, or click it again to undo. Used GUIDs are shown struck through.
4. If you need more GUIDs, click **Extend List**. It reserves the number of GUIDs from the field directly after the last GUID of the list. If those are taken, it uses the next continuous free block after it.
5. When the mod is finished, register it in the **GUID Database** tab, or drop it onto the window while this tab is shown. Reserved GUIDs that are now in the database show as **registered**, together with their comment.
6. Click **Clean Up** to remove the registered GUIDs from the list and release the unused ones. Used GUIDs that are not registered yet stay reserved.

| Action | How |
|---|---|
| Mark as used / free | Click the ☐ box, or right-click → **Mark as used** / **Mark as free** |
| Planning comment | Double-click the **Comment** cell, press `F2`, or right-click → **Edit comment**. `Enter` saves, `Esc` cancels. When the mod is registered, its own comment replaces yours; if it has none, your comment is taken over into the database. |
| Copy | Double-click, `Ctrl+C`, or right-click → **Copy** (several GUIDs are copied one per line) |
| Remove from list | `Del` key or right-click → **Remove from list**. This releases the GUIDs. |
| Select all | `Ctrl+A` |

Reserved GUIDs, both free and used, are never suggested again, in any list. They are also skipped when the **Replace Dummy GUIDs** tab assigns real GUIDs. So two projects never get the same GUID. The lists are stored per game and kept when you close the tool.

#### Tab "Replace Dummy GUIDs"

1. Open the mod with **Open Folder** or **Open ZIP**, or drag the mod folder / ZIP onto the window while this tab is shown (Windows, one mod at a time).
   - By default, all GUIDs inside a dummy range are listed in an interactive table with checkboxes (`☑` / `☐`).
   - Check **Replace all GUIDs not in own ranges** if you want to find and replace all numeric GUIDs in the mod that lie outside your own ranges instead.
2. Select which GUIDs to replace:
   - Click a row's checkbox (`☑` / `☐`) or press `Space` to toggle replacement selection for highlighted rows.
   - Right-click highlighted rows to choose **Select for replacement** or **Deselect for replacement**.
   - Right-click a row and choose **Copy GUID** to copy the selected GUIDs to the clipboard (one per line).
   - Use **Select All** / **Deselect All** buttons (or click the **Replace** table heading) to toggle all items.
3. Choose where assignment starts:
   - **Automatic:** start at the first own GUID and fill all free gaps.
   - **Start GUID:** start at a value you enter.
4. Click **Assign & Replace Real GUIDs** and confirm the warning.

What happens:

- Selected GUIDs are assigned in ascending order to the next free GUID.
- If one own range is full, assignment continues in the next range.
- Every standalone occurrence of a replaced GUID is updated in all XML files. This includes `<GUID>`, references such as `<Product>`, ModOp attributes and `GUID - text` comments.
- Nothing is changed if there are not enough free GUIDs, or if you cancel.
- Afterwards, the tool offers to register the mod in the database.

> ⚠️ Files are overwritten directly and this **cannot be undone**. Keep a backup or use version control.

#### Tab "Settings"

| Sub tab | Content |
|---|---|
| **General** | Appearance mode, color theme (needs a restart), language, Language Comment (language file for names, saved with Enter or when leaving the field) |
| **Anno 117** | Own GUID ranges and dummy GUID ranges for Anno 117 |
| **Anno 1800** | Own GUID ranges and dummy GUID ranges for Anno 1800 |

How to edit ranges:

- **`+`** adds a row and **`✕`** removes it.
- **Save Ranges** saves both lists of that game. `Enter` in a field does the same.

Rules checked when you save:

- Start and end must be numbers, with start ≤ end.
- Each list needs at least one range.
- Ranges within one list must not overlap.
- Own ranges and dummy ranges of the same game must not overlap. Ranges of different games may overlap.

### Files

| File | Location | Content |
|---|---|---|
| `config.ini` | Working directory | General settings and GUID ranges per game |
| `guid_database_anno117.json` | Working directory | GUID database for Anno 117 |
| `guid_database_anno1800.json` | Working directory | GUID database for Anno 1800 |
| `guid_reservations_anno117.json` / `guid_reservations_anno1800.json` | Working directory | GUIDs reserved in the **Free GUIDs** tab, one list per mod project, per game |
| `version.txt` | Next to `main.py` (or the `.exe`) | Program version shown in the title, e.g. `v1.23.45` |

Example `config.ini`:

```ini
[SETTINGS]
appearance_mode = Dark
color_theme = dark-blue
language = en
auto_assign = false
mark_used_on_copy = true
show_reserved_in_db = true
comment_language = english
active_game = anno1800

[ANNO1800]
own_ranges = 1337471142-1337471999, 2144009900-2144009999
dummy_ranges = 1000000000-1000999999
```

Example database entry:

```json
"2144009900": {
    "comment": "Praefectus Specialists Name",
    "locations": ["data/config/gui/texts_*.xml"]
}
```

**Migration from older versions** happens automatically:

- An old `guid_database.json` becomes the Anno 1800 database. The original file is kept as `guid_database.json.bak`.
- Old single-range settings are converted to range lists.
- Old database entries are converted to the new format.

### Project structure

```
AnnoGUIDTool/
├── main.py                 Entry point
├── app.py                  Main window, game selector, translation, tab wiring
├── version.txt             Program version
├── core/
│   ├── constants.py        Program info, file names, default ranges, regex patterns
│   ├── translations.py     All UI texts (DE / EN)
│   ├── collisions.py       Find GUIDs defined in more than one mod
│   ├── config_manager.py   config.ini, GUID range lists per game
│   ├── file_drop.py        Drag & drop from the Explorer (Win32 via ctypes)
│   ├── guid_database.py    JSON database, free GUID allocation, migration
│   ├── guid_reservations.py GUIDs reserved in the "Free GUIDs" tab
│   ├── xml_scanner.py      Read and rewrite XML files in folders and ZIPs
│   └── version.py          Reads version.txt
├── dialogs/
│   ├── collision_dialog.py Import: migrate or accept colliding GUIDs
│   ├── collision_report.py Result of "Check Collisions"
│   ├── migrate_dialog.py   Right-click "Migrate a mod to a free GUID…"
│   └── update_dialog.py    "New version available" popup
└── tabs/
    ├── database_tab.py     Tab "GUID Database"
    ├── reserve_tab.py      Tab "Free GUIDs"
    ├── replace_tab.py      Tab "Replace Dummy GUIDs"
    └── settings_tab.py     Tab "Settings"
```

The modules in `core/` have no UI code. All code is documented in English.

**Customization:**

- Column widths of the GUID table: constants at the top of `tabs/database_tab.py`
- Program name and author: `core/constants.py`

### Author

**gz2k2**

---

<a name="deutsch"></a>

## Deutsch

Ein Desktop-Tool für Modder von **Anno 117** und **Anno 1800**. Es verwaltet die GUIDs, die deine Mods verwenden, und ersetzt temporäre Dummy-GUIDs durch echte, freie GUIDs aus deinen eigenen GUID Ranges.

### Funktionen

- **Zwei Spiele, zwei Datenbanken.** Anno 117 und Anno 1800 haben jeweils eine eigene GUID-Datenbank und eigene GUID Ranges. Das Spiel wählst du über die Auswahl oberhalb der Tabs.
- **GUID-Datenbank.**
  - Mods aus einem Ordner oder einem ZIP-Archiv registrieren, oder per Drag & Drop ins Fenster ziehen (Windows).
  - Nach GUID, Kommentar oder Dateipfad suchen.
  - Nach GUID oder Ort sortieren, auf- oder absteigend.
  - Als CSV exportieren.
  - Einträge löschen.
  - Einträge in das andere Spiel verschieben.
- **Kommentare.** Kommentare im Format `GUID - Text` in XML-Kommentaren werden beim Registrieren gelesen und in einer eigenen Spalte angezeigt.
- **Freie GUID-Blöcke.** Einen zusammenhängenden Block freier GUIDs für eine Mod holen, an der du noch schreibst. Die GUIDs bleiben reserviert, bis die Mod importiert ist.
- **Dummy-GUIDs ersetzen.** Dummy-GUIDs einer Mod werden durch freie GUIDs aus den eigenen Ranges ersetzt. Definitionen und alle Verweise werden angepasst.
- **Mehrere GUID Ranges pro Spiel.** Für jedes Spiel kannst du beliebig viele eigene Ranges und Dummy Ranges festlegen.
- **Schutz vor Doppelvergabe.** Bereits registrierte oder reservierte GUIDs werden nie erneut vergeben.
- **Kollisionsprüfung.** Warnt, wenn eine Mod beim Registrieren eine GUID einer anderen Mod verwendet, eine GUID doppelt definiert oder eine für ein anderes Projekt reservierte GUID nutzt: auf eine freie GUID migrieren oder akzeptieren und markiert lassen. Ein Ordner mit Mods lässt sich auch prüfen, ohne etwas zu registrieren.
- **Oberfläche auf Deutsch und Englisch.** Helles, dunkles und System-Design stehen zur Wahl.

### Voraussetzungen

- Python 3 mit Tkinter (im Standard-Installer für Windows enthalten)
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)

```bash
pip install customtkinter
```

### Start

```bash
python main.py
```

Beim ersten Start:

1. Unter **Einstellungen → Anno 117 / Anno 1800** die eigenen GUID Ranges und die Dummy GUID Ranges eintragen.
2. Oben das Spiel auswählen.
3. Im Tab **GUID Datenbank** die vorhandenen Mods registrieren. So sind ihre GUIDs bekannt und werden nie erneut vergeben.

### Bedienung

#### Tab „GUID Datenbank“

| Aktion | So geht's |
|---|---|
| Mod registrieren | **Ordner in DB registrieren** oder **ZIP in DB registrieren** |
| Per Drag & Drop registrieren | Einen oder mehrere Mod-Ordner / ZIP-Dateien aus dem Explorer ins Fenster ziehen (nur Windows). Das Tool wechselt in diesen Tab und zeigt eine Zusammenfassung für alle Mods. Andere Dateien werden ignoriert. Funktioniert in jedem Tab außer **Dummy-GUIDs Ersetzen** (dort öffnet das Ziehen die Mod stattdessen). |
| Suchen | In das Suchfeld tippen. Es filtert nach GUID, Kommentar und Ort. |
| Reservierte GUIDs anzeigen | **Reservierte anzeigen** zeigt die in den Listen **Freie GUIDs** reservierten, noch nicht registrierten GUIDs: eine blaue Zeile pro zusammenhängendem Bereich und Projekt, mit dem Projektnamen als Kommentar. Rechtsklick → **In „Freie GUIDs“ anzeigen** öffnet das Projekt. Löschen und Verschieben ignorieren diese Zeilen. |
| GUIDs kopieren | Eine oder mehrere Zeilen auswählen → Rechtsklick → **GUID kopieren**. Die ausgewählten GUIDs werden zeilenweise kopiert. |
| Sortieren | Auf die Spaltenüberschrift **GUID** oder **Ort** klicken. Ein weiterer Klick kehrt die Reihenfolge um (▲ aufsteigend, ▼ absteigend). |
| Exportieren | **Export .csv** schreibt `GUID;Kommentar;Ort`, getrennt durch `;` (UTF-8) |
| Löschen | Button, `Entf`-Taste oder Rechtsklick-Menü |
| Alle auswählen | `Strg+A` |
| In anderes Spiel verschieben | Rechtsklick → **Verschieben nach Anno 117 / Anno 1800** |
| Kollidierende GUID migrieren | Rechtsklick auf eine rote GUID → **Eine Mod auf freie GUID migrieren…** |
| Auf GUID-Kollisionen prüfen | **Kollisionen prüfen**, dann einen Ordner mit Mods wählen. Es wird nichts registriert. |
| Waagerecht scrollen | Scrollbalken oder `Shift` + Mausrad |

Beim Registrieren einer Mod:

- Registriert werden nur GUIDs, die in `<GUID>`- oder `<LineId>`-Tags definiert sind.
- Sie müssen in einer der **eigenen GUID Ranges** des aktiven Spiels liegen.
- Sprachdateien (`texts_english.xml`, `texts_german.xml`, …) werden zu `texts_*.xml` zusammengefasst.

**Kommentare.** Die Kommentarspalte wird aus XML-Kommentaren gefüllt, die pro Zeile einen Eintrag `GUID - Text` enthalten:

```xml
<!--
2144009900 - Praefectus Specialists Name
2144009901 - Praefectus Specialists Description
-->
<!-- 2144009902 - Praefectus Adriana Name -->
```

- Ein Kommentar kann in einer beliebigen XML-Datei derselben Mod stehen.
- Als Trennzeichen gelten normale Bindestriche, Gedankenstriche (`–`, `—`) und geschützte Leerzeichen.
- Ein beim Registrieren gefundener Kommentar überschreibt den gespeicherten. GUIDs ohne Kommentar in der Mod behalten ihren gespeicherten Kommentar.
- Nach dem Import zeigt eine Übersicht, wie viele Kommentare gefunden, geändert, unverändert oder übersprungen und wie viele Namen übernommen wurden.

**Namen als Ersatz.** Hat eine GUID keinen `GUID - Text`-Kommentar, wird stattdessen ihr Name verwendet:

1. `<Name>` aus dem `<Standard>`-Block des Assets (Anno 117 und Anno 1800)
2. `<Text>` des Eintrags in einer `texts_*.xml`. Beide Aufbauten werden erkannt: Text vor `<LineId>` (Anno 117) und `<GUID>` vor Text (Anno 1800). Die Sprachdatei legst du unter **Einstellungen → Allgemein → Sprache Kommentare** fest (z. B. `german` → `texts_german.xml`). Fehlt diese Datei oder enthält sie die GUID nicht, wird `texts_english.xml` verwendet, danach jede andere Sprache.

Ein Name wird nur gespeichert, wenn die GUID in der Datenbank noch keinen Kommentar hat. Er überschreibt also nie einen vorhandenen Kommentar.

**Verschieben.** Kommentar und Dateipfade wandern zusammen mit der GUID mit. Gibt es die GUID im Ziel schon, werden die Dateipfade zusammengeführt.

**GUID-Kollisionen.** Die Mod einer Datei ist der Ordner direkt über `data/`, z. B. `[Specialists] v2/data/...`. Bei einer ZIP ohne diesen Ordner wird der Dateiname der ZIP verwendet. Beim Registrieren einer Mod werden drei Arten von Kollisionen erkannt:

- **In einer anderen Mod definiert:** Die Datenbank führt die GUID bereits für eine andere Mod.
- **In der Mod mehrfach definiert:** Die GUID hat zwei Asset-Definitionen (`<Standard>`-Blöcke, in derselben oder in verschiedenen Dateien) oder zwei Einträge in derselben `texts_*.xml`. Ein Asset und sein eigener Texteintrag teilen sich die GUID absichtlich; das ist keine Kollision. Auskommentiertes XML wird ignoriert.
- **In einem anderen Projekt reserviert:** Die GUID ist in der Liste **Freie GUIDs** eines anderen Mod-Projekts reserviert. Als eigenes Projekt der Mod gilt die im Tab **Freie GUIDs** gewählte Liste, sofern sie GUIDs der Mod enthält, sonst die Liste mit den meisten davon. Der Dialog nennt die angenommene Liste.

Ein Dialog listet die kollidierenden GUIDs mit allen Problemen. Pro GUID wählst du:

- **Migrieren:** Die registrierte Mod bekommt die vorgeschlagene freie GUID. Jedes Vorkommen der alten GUID in den Dateien dieser Mod wird ersetzt, auch Definitionen, Verweise und `GUID - Text`-Kommentare. Andere Mods bleiben unverändert. Du bestätigst das vorher, da es nicht rückgängig zu machen ist. Bei mehrfach definierten GUIDs nicht möglich: Das Tool kann nicht wissen, welche Definition sich ändern soll; korrigiere diese in der Mod.
- **Akzeptieren:** Die GUID wird trotzdem eingetragen. Gedacht für alternative Versionen einer Mod, die nie zusammen geladen werden. Akzeptierte Kollisionen werden nicht erneut gemeldet. Bei einer Reservierung in einem anderen Projekt: Hat dieses Projekt die GUID noch nicht benutzt, wird seine Reservierung freigegeben. Hat es sie benutzt, bleibt die GUID markiert, solange sie dort reserviert ist.

Jede GUID steht zu Beginn auf **Akzeptieren**. **Auf Migrieren setzen** und **Auf Akzeptieren setzen** ändern nur die Entscheidung der ausgewählten Zeilen, ohne Auswahl die aller Zeilen. Die Statuszeile unter der Tabelle zeigt die aktuellen Entscheidungen. **Import fortsetzen** wendet sie an und registriert die Mod. **Import abbrechen** überspringt diese Mod. Die Zusammenfassung listet jede migrierte GUID als `alt → neu`.

Kollidierende GUIDs erscheinen in der Tabelle **rot mit `!`**, und die Statistikzeile zeigt ihre Anzahl. Eine Mehrfach-Definition in einer Mod verliert ihre Markierung, sobald du die korrigierte Mod erneut registrierst.

**Später migrieren.** Rechtsklick auf eine rote GUID → **Eine Mod auf freie GUID migrieren…**. Der Dialog listet die Mods, die die GUID definieren (die zuletzt registrierte ist ausgewählt), und zeigt die vorgeschlagene freie GUID. Die Datenbank speichert nur relative Pfade, daher wählst du danach den Ordner oder die ZIP der gewählten Mod. Nach deiner Bestätigung wird die GUID nur in den Dateien dieser Mod ersetzt, die alten Pfade der Mod werden von der GUID entfernt und die Mod wird neu registriert. Mods, die die GUID selbst mehrfach definieren, können nicht migriert werden.

Akzeptierst du eine Kollision mit einer anderen Mod, bleibt der Kommentar der Mod erhalten, die die GUID zuerst hatte.

**Kollisionen prüfen.** Prüft einen Ordner mit vielen Mods, Ordner und ZIP-Dateien in beliebiger Tiefe, ohne etwas zu registrieren. Geprüft wird jede numerische GUID, nicht nur deine eigenen Ranges. So kannst du auch die Arbeit anderer Modder prüfen. Der Bericht listet:

- GUIDs, die in mehr als einer der geprüften Mods definiert sind
- GUIDs, die eine geprüfte Mod mehrfach definiert
- GUIDs der geprüften Mods, die deine Datenbank für andere Mods führt
- GUIDs der geprüften Mods, die in deinen Listen **Freie GUIDs** reserviert sind

Der Bericht lässt sich als CSV exportieren.

#### Tab „Freie GUIDs“

Dieser Tab hilft, wenn du gerade an einer Mod schreibst und sofort echte GUIDs brauchst.

**Mod-Projekte.** Reservierte GUIDs liegen in einer Liste pro Mod-Projekt. Die Liste wählst du unter **Mod-Projekt**; mit **Neu**, **Umbenennen** und **Löschen** legst du Listen an, benennst sie um oder löschst sie. Alles Weitere bezieht sich auf die gewählte Liste. Gibt es noch keine Liste, legt der erste Klick auf **Freien Block vorschlagen** eine an („Meine Mod“). Beim Löschen einer Liste werden ihre GUIDs freigegeben.

1. Die **Anzahl GUIDs** eingeben und **Freien Block vorschlagen** klicken. Das Tool reserviert den ersten zusammenhängenden Block freier GUIDs in deinen eigenen Ranges. Registrierte oder bereits reservierte GUIDs werden übersprungen.
2. Die GUIDs nacheinander in die Mod kopieren:
   - **Nächste freie GUID kopieren** kopiert die niedrigste freie GUID der Liste.
   - Doppelklick auf eine Zeile (außerhalb der Zelle **Kommentar**), oder Zeilen auswählen und `Strg+C` drücken.
   - Mit **Beim Kopieren als benutzt markieren** (standardmäßig an) wird eine kopierte GUID sofort als benutzt markiert.
3. Auf das **☐** einer Zeile klicken, um sie als benutzt zu markieren; ein weiterer Klick macht das rückgängig. Benutzte GUIDs werden durchgestrichen.
4. Wenn du mehr GUIDs brauchst, **Liste erweitern** klicken. Es reserviert die Anzahl aus dem Feld direkt nach der letzten GUID der Liste. Sind diese belegt, wird der nächste zusammenhängende freie Block danach verwendet.
5. Wenn die Mod fertig ist, sie im Tab **GUID Datenbank** registrieren oder ins Fenster ziehen, während dieser Tab angezeigt wird. Reservierte GUIDs, die jetzt in der Datenbank stehen, werden als **registriert** angezeigt, zusammen mit ihrem Kommentar.
6. **Aufräumen** entfernt die registrierten GUIDs aus der Liste und gibt die unbenutzten wieder frei. Benutzte, noch nicht registrierte GUIDs bleiben reserviert.

| Aktion | So geht's |
|---|---|
| Als benutzt / frei markieren | Auf das ☐ klicken, oder Rechtsklick → **Als benutzt markieren** / **Als frei markieren** |
| Planungs-Kommentar | Doppelklick auf die Zelle **Kommentar**, `F2` oder Rechtsklick → **Kommentar bearbeiten**. `Enter` speichert, `Esc` bricht ab. Beim Registrieren der Mod ersetzt ihr eigener Kommentar deinen; hat sie keinen, wird dein Kommentar in die Datenbank übernommen. |
| Kopieren | Doppelklick, `Strg+C` oder Rechtsklick → **Kopieren** (mehrere GUIDs werden zeilenweise kopiert) |
| Aus der Liste entfernen | Taste `Entf` oder Rechtsklick → **Aus der Liste entfernen**. Die GUIDs werden dadurch freigegeben. |
| Alles auswählen | `Strg+A` |

Reservierte GUIDs, freie wie benutzte, werden in keiner Liste erneut vorgeschlagen. Auch der Tab **Dummy-GUIDs Ersetzen** überspringt sie bei der Vergabe. So bekommen zwei Projekte nie dieselbe GUID. Die Listen werden pro Spiel gespeichert und bleiben beim Schließen des Tools erhalten.

#### Tab „Dummy-GUIDs Ersetzen“

1. Die Mod mit **Ordner öffnen** oder **ZIP öffnen** laden, oder den Mod-Ordner / die ZIP ins Fenster ziehen, während dieser Tab angezeigt wird (Windows, eine Mod auf einmal).
   - Standardmäßig werden alle GUIDs innerhalb einer Dummy Range in einer interaktiven Tabelle mit Checkboxen (`☑` / `☐`) aufgelistet.
   - Aktiviere **Alle GUIDs ersetzen, die nicht in eigenen Ranges liegen**, wenn stattdessen alle numerischen GUIDs der Mod gesucht und ersetzt werden sollen, die außerhalb deiner eigenen Ranges liegen.
2. Anpassen, welche GUIDs ersetzt werden sollen:
   - Auf das **`☑` / `☐`** einer Zeile klicken oder die **Leertaste** drücken, um die Auswahl markierter Zeilen umzuschalten.
   - Rechtsklick auf markierte Zeilen → **Für Ersetzung auswählen** oder **Von Ersetzung abwählen**.
   - Rechtsklick auf eine Zeile → **GUID kopieren**, um die ausgewählten GUIDs in die Zwischenablage zu kopieren (eine pro Zeile).
   - Mit den Buttons **Alle auswählen** / **Keine auswählen** (oder Klick auf die Tabellenüberschrift **Ersetzen**) alle Zeilen umschalten.
3. Festlegen, wo die Vergabe beginnt:
   - **Automatisch:** ab der ersten eigenen GUID, freie Lücken werden gefüllt.
   - **Start-GUID:** ab einem selbst eingegebenen Wert.
4. **Echte GUIDs zuweisen & Ersetzen** klicken und die Warnung bestätigen.

Was dabei passiert:

- Die ausgewählten GUIDs erhalten in aufsteigender Reihenfolge die jeweils nächste freie GUID.
- Ist eine eigene Range voll, geht es in der nächsten Range weiter.
- Jedes alleinstehende Vorkommen einer ersetzten GUID wird in allen XML-Dateien aktualisiert. Das umfasst `<GUID>`, Verweise wie `<Product>`, ModOp-Attribute und `GUID - Text`-Kommentare.
- Reichen die freien GUIDs nicht aus oder brichst du ab, wird nichts verändert.
- Danach bietet das Tool an, die Mod in der Datenbank zu registrieren.

> ⚠️ Die Dateien werden direkt überschrieben. Das lässt sich **nicht rückgängig machen**. Lege vorher ein Backup an oder nutze eine Versionsverwaltung.

#### Tab „Einstellungen“

| Untertab | Inhalt |
|---|---|
| **Allgemein** | Erscheinungsbild, Farbthema (Neustart nötig), Sprache, Sprache Kommentare (Sprachdatei für Namen, gespeichert mit Enter oder beim Verlassen des Feldes) |
| **Anno 117** | Eigene GUID Ranges und Dummy GUID Ranges für Anno 117 |
| **Anno 1800** | Eigene GUID Ranges und Dummy GUID Ranges für Anno 1800 |

So bearbeitest du Ranges:

- **`+`** fügt eine Zeile hinzu, **`✕`** entfernt sie.
- **Ranges speichern** speichert beide Listen des Spiels. `Enter` in einem Feld macht dasselbe.

Diese Regeln werden beim Speichern geprüft:

- Start und Ende müssen Zahlen sein, mit Start ≤ Ende.
- Jede Liste braucht mindestens eine Range.
- Ranges innerhalb einer Liste dürfen sich nicht überschneiden.
- Eigene Ranges und Dummy Ranges desselben Spiels dürfen sich nicht überschneiden. Ranges verschiedener Spiele dürfen sich überschneiden.

### Dateien

| Datei | Ort | Inhalt |
|---|---|---|
| `config.ini` | Arbeitsverzeichnis | Allgemeine Einstellungen und GUID Ranges pro Spiel |
| `guid_database_anno117.json` | Arbeitsverzeichnis | GUID-Datenbank für Anno 117 |
| `guid_database_anno1800.json` | Arbeitsverzeichnis | GUID-Datenbank für Anno 1800 |
| `guid_reservations_anno117.json` / `guid_reservations_anno1800.json` | Arbeitsverzeichnis | Im Tab **Freie GUIDs** reservierte GUIDs, eine Liste pro Mod-Projekt, pro Spiel |
| `version.txt` | Neben `main.py` (bzw. der `.exe`) | Programmversion für die Titelleiste, z. B. `v1.23.45` |

Die Formate von `config.ini` und den Datenbanken findest du oben im englischen Teil unter [Files](#files).

**Übernahme aus älteren Versionen** erfolgt automatisch:

- Eine alte `guid_database.json` wird zur Anno 1800-Datenbank. Die Originaldatei bleibt als `guid_database.json.bak` erhalten.
- Alte Einzel-Ranges werden in Range-Listen umgewandelt.
- Alte Datenbankeinträge werden ins neue Format umgestellt.

### Projektstruktur

```
AnnoGUIDTool/
├── main.py                 Startpunkt
├── app.py                  Hauptfenster, Spielauswahl, Übersetzung, Verbindung der Tabs
├── version.txt             Programmversion
├── core/
│   ├── constants.py        Programminfo, Dateinamen, Standard-Ranges, Regex
│   ├── translations.py     Alle Texte (DE / EN)
│   ├── collisions.py       GUIDs finden, die in mehreren Mods definiert sind
│   ├── config_manager.py   config.ini, GUID Range-Listen pro Spiel
│   ├── file_drop.py        Drag & Drop aus dem Explorer (Win32 über ctypes)
│   ├── guid_database.py    JSON-Datenbank, Vergabe freier GUIDs, Migration
│   ├── guid_reservations.py Im Tab „Freie GUIDs“ reservierte GUIDs
│   ├── xml_scanner.py      XML-Dateien in Ordnern und ZIPs lesen und schreiben
│   └── version.py          Liest version.txt
├── dialogs/
│   ├── collision_dialog.py Import: kollidierende GUIDs migrieren oder akzeptieren
│   ├── collision_report.py Ergebnis von „Kollisionen prüfen“
│   ├── migrate_dialog.py   Rechtsklick „Eine Mod auf freie GUID migrieren…“
│   └── update_dialog.py    Hinweis „Neue Version verfügbar“
└── tabs/
    ├── database_tab.py     Tab „GUID Datenbank“
    ├── reserve_tab.py      Tab „Freie GUIDs“
    ├── replace_tab.py      Tab „Dummy-GUIDs Ersetzen“
    └── settings_tab.py     Tab „Einstellungen“
```

Die Module in `core/` enthalten keinen Oberflächen-Code. Der gesamte Code ist auf Englisch dokumentiert.

**Anpassungen:**

- Spaltenbreiten der GUID-Tabelle: Konstanten oben in `tabs/database_tab.py`
- Programmname und Autor: `core/constants.py`

### Autor

**gz2k2**
