# Validation

## Completed in the build environment

- Python syntax compilation for every application module
- Eleven passing automated tests
- Required state classification: menu, game, buy time, spectating, bomb planted
- Round-over and warmup classification
- Kill-streak increment and round reset
- Steam `libraryfolders.vdf` parsing
- Local tokenized GSI generation
- Local listener authentication behavior
- Profile creation, rename, persistence, switching, and deletion
- Appearance migration, normalization, and persistence

## Requires a Windows release check

The current build environment does not provide Windows, CS2, Windows audio sessions, PySide6 runtime plugins, or Inno Setup. Before publishing a binary, run the Windows checklist:

1. Launch the source build on Windows 10 and Windows 11.
2. Verify automatic CS2 discovery on default and secondary Steam libraries.
3. Verify first-run GSI installation and repair.
4. Test Spotify, YouTube Music, Firefox, and one additional media player.
5. Test each state in live CS2 and compare with the local simulator.
6. Build with `build_release.ps1` and install/uninstall the Inno Setup package.
7. Scan the release archive and installer, then code-sign the public build.
8. Verify the frameless title bar supports move, double-click maximize, restore, resize, minimize, and close.
9. Verify every button, profile card, combo box, checkbox, and slider displays the pointing cursor where appropriate.
10. Test Album Dynamic with artwork from at least Spotify, YouTube Music, and a browser source; verify fallback when artwork is absent.
11. Verify profile cards and the title-bar selector switch immediately and Ctrl+1 through Ctrl+5 activate the expected profiles.
12. Change every appearance setting, restart, and confirm persistence and semantic bomb/warning colors.
