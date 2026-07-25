# Changelog

## 0.2.5

- Fixed silent Kill Streaks Test buttons after the installer-size optimization.
- Replaced the unreliable local-file WinRT MediaPlayer path with Windows MCI for asynchronous WAV and MP3 playback.
- Added unique MCI aliases so rapid tests and kill sounds can overlap.
- Added visible runtime error feedback when Windows rejects an audio file instead of failing silently.
- Added automatic repair of stale absolute paths in the three bundled kill-streak profiles when the source folder or installation directory changes.
- Preserved user-selected custom sounds while repairing only missing bundled paths.
- Removed the now-unused WinRT Media Core and Media Playback packages and PyInstaller hidden imports.

## 0.2.4

- Added the repository banner and a GitHub-ready social preview image outside the packaged application assets.
- Added a practical distribution and launch checklist.
- Replaced the full `PySide6` dependency with `PySide6-Essentials`.
- Added automatic removal of stale `PySide6` and `PySide6-Addons` packages from existing development/build environments.
- Replaced QtMultimedia sound playback with the built-in Windows MediaPlayer API for overlapping WAV/MP3 playback.
- Disabled Windows media-command integration for event sounds so they do not replace the user's active music session.
- Added explicit PyInstaller exclusions for unused Qt multimedia, QML, Quick, SQL, test, and UI-loader modules.
- Added a separate runtime-pruning step for unused Qt plugin trees and build artifacts.
- Enabled stronger Inno Setup compression and post-build size reporting.
- Included the uploaded VALORANT and Reaver default sound files in the source package.

## 0.2.3

- Separated music/audio profiles from kill-streak sound profiles in storage, runtime state, and the interface.
- Kept the existing Profiles page and title-bar selector dedicated to music profiles.
- Added an independent sound-profile selector and local management controls to the Kill Streaks page.
- Added the three bundled kill-streak profiles: **VALORANT**, **Reaver**, and **Tones**.
- Added automatic migration of pre-0.2.3 embedded kill-streak settings without losing custom paths or volume.
- Added MP3 playback through Qt Multimedia while retaining the low-latency WAV path.
- Expanded kill-streak file selection to WAV and MP3.
- Removed the pinned Python-version invocation from `setup_dev.bat`; it now uses the installed Python launcher/interpreter.

## 0.2.2

- Simplified `run_dev.bat` into a detached `pythonw.exe` launcher with no environment check or persistent command prompt.
- Added `setup_dev.bat` for explicit one-time environment creation and dependency installation.
- Removed creator aliases from application metadata, About, README, and release messaging.
- Replaced the About credit links with reusable obround GitHub and Discord identity controls.
- The GitHub identity opens `notskrillence/CS2-Music-Controller`; the Discord identity copies `skrilll`.
- Kept production PyInstaller builds in windowed mode so the installed application does not open a console.

## 0.2.1

- Fixed frameless-window teleporting by preventing the native system move and manual fallback from running simultaneously.
- Replaced character-based minimize, maximize, restore, close, overflow, and repository controls with painter-drawn Material-style icons.
- Increased title-bar control targets and added rounded hover and pressed state layers.
- Added custom-painted audio sliders with centered geometry, direct click-and-drag behavior, and sufficient vertical space to prevent clipping.
- Added a rounded custom progress indicator and refined both vertical and horizontal scrollbars.
- Clipped album artwork to its rounded surface and replaced the fallback music glyph with a painter-drawn media mark.
- Replaced square color and kill-streak markers with circular components.
- Added a GitHub shortcut, an About page, project credit for skrilll, license information, and repository metadata.
- Split every UI page into its own module and introduced a route-based navigation registry for safer future expansion.
- Standardized font weights, selected Fusion for consistent Qt metrics, and removed remaining symbol-font dependencies.
- Expanded automated coverage to 12 tests.

## 0.2.0

- Replaced the developer-dashboard appearance with a near-AMOLED Material-inspired role system.
- Added a frameless integrated title bar with native move, resize, maximize, minimize, and close controls.
- Added one-click profile cards, title-bar profile switching, rename/import/export, and Ctrl+1 through Ctrl+5 shortcuts.
- Added Appearance controls for album dynamic, branded dark, and custom seed themes.
- Added low-frequency Windows media metadata and album-art monitoring with bounded reads and artwork-hash caching.
- Added album-aware accents and a restrained now-playing aura while preserving semantic bomb, warning, success, and error colors.
- Standardized typography on Segoe UI Variable/Segoe UI and removed external font dependencies.
- Added pointing cursors, focus states, disabled states, and short optional page/profile transitions.
- Split reusable theme, media, title-bar, resize, and profile components into dedicated modules.
- Expanded automated coverage to 11 tests.

## 0.1.0

- Initial native Windows application foundation.
