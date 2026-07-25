# Validation

## Completed in the build environment

- Python syntax compilation for every application module
- Fourteen passing automated tests
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
8. Verify the frameless title bar follows the pointer without jumping, supports Windows snapping, double-click maximize, restore, resize, minimize, and close.
9. Verify every button, profile card, combo box, checkbox, and slider displays the pointing cursor where appropriate.
10. Test Album Dynamic with artwork from at least Spotify, YouTube Music, and a browser source; verify fallback when artwork is absent.
11. Verify profile cards and the title-bar selector switch immediately and Ctrl+1 through Ctrl+5 activate the expected profiles.
12. Change every appearance setting, restart, and confirm persistence and semantic bomb/warning colors.
13. Inspect every audio slider at 100%, 125%, 150%, and 200% Windows display scaling; confirm the handle and track are vertically centered and never clipped.
14. Confirm title-bar controls have consistent Segoe typography around them, painter-drawn icons, adequate hit targets, hover states, and no symbol-font fallback.
15. Open the title-bar repository shortcut and GitHub obround; confirm both point to `notskrillence/CS2-Music-Controller`. Click the Discord obround and confirm it copies `skrilll`.
16. Verify album artwork is rounded rather than rendered as a square inside its card.

17. Launch with `run_dev.bat`; confirm the command prompt closes immediately while the GUI remains open.
18. Launch the packaged executable; confirm no console window is created.

19. Switch among VALORANT, Reaver, and Tones and confirm the audio profile remains unchanged.
20. Test all five MP3 steps in VALORANT and Reaver plus all five WAV steps in Tones.
21. Upgrade from a pre-0.2.3 AppData directory and confirm embedded kill-streak settings migrate to an independent sound profile.
22. Test one WAV and one MP3 sound and confirm neither replaces the user's active Windows media session.
23. Build a release and record the portable and installer sizes printed by `build_release.ps1`.
24. Confirm `dist\CS2MusicController` contains no QtMultimedia DLLs or plugins.

25. Test WAV and MP3 buttons in all three bundled kill-streak profiles and confirm Windows MCI playback overlaps without opening a media-control session.
