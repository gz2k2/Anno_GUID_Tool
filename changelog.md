# Changelog

## v0.7.0

### Added
- **New "Mod Package" tab** directly after the GUID Database tab.
- **Mod Package management** with a drop-down and New, Rename, and Delete actions.
- **Multiple GUID ranges per Mod Package** using GUID Start and GUID End fields with add (+) and remove (-) controls.
- **Mod Package range table** with the columns Mod Package and GUID Range. The table shows only ranges of the selected package, supports multiple selection, provides a right-click Remove action, and adjusts column widths dynamically to visible content.
- **Package View in GUID Database**: optional grouped display of registered GUIDs by Mod Package range. Package rows are displayed in green and use the Mod Package name as comment.
- **Add to Mod Package** in the GUID Database right-click menu for single or multiple selected GUID entries. Existing packages can be selected in a dialog; missing GUIDs are added and adjacent GUIDs are merged into ranges.
- **Convert to Mod Package** in the right-click menu for Free GUIDs rows in the GUID Database. The Free GUIDs project name is used as the package name, all project GUIDs are registered in the GUID Database, planning comments are retained for new database entries, and the source Free GUIDs project is removed after successful conversion.
- **Custom start GUID in Free GUIDs** with a "Use own start GUID" checkbox and conditional input field between Mod Project and Number of GUIDs. The complete requested block is checked for database and reservation collisions before it is created.
- **Multi-row comment editing in Free GUIDs**: "Edit comment (F2)" now applies the entered comment to every selected row.


