# Architecture

## Design goals

1. Keep the GSI request path short and non-blocking.
2. Keep Windows COM and audio operations off the Qt interface thread.
3. Persist configuration atomically so a crash cannot leave half-written JSON.
4. Treat the CS2 installation path and generated GSI file as repairable setup state.
5. Keep the native interface independent from the local HTTP transport.
6. Apply theme changes only on user input or track changes; never run a permanent animation or palette loop.
7. Keep reusable shell, theme, media, and profile components outside the page implementation.
8. Keep each page in an isolated module and register navigation routes through one shell method.
9. Prefer painter-drawn icons and controls over font glyphs or platform-dependent subcontrol geometry.

## Runtime flow

`GSIServer` binds only to `127.0.0.1`. Its handler validates the per-install token and passes decoded JSON to `RuntimeController`.

`GameStateResolver` reduces payloads into one stable state and detects increases in `player.state.round_kills`. It resets the stored kill count when `map.round` changes.

`RuntimeController` takes separate thread-safe snapshots for the active audio profile and active kill-streak profile. State changes enqueue one volume command and optionally request a state sound. Kill increases consult only the independent kill-streak profile, so switching music profiles cannot change the selected sound pack.

`MediaVolumeController` owns a dedicated COM thread. It keeps only the newest pending command and interrupts a fade when a newer command arrives. This prevents a queue of obsolete volume transitions during rapid state changes.

Qt signals carry snapshots, logs, audio-session lists, media metadata, and sound requests back to the interface thread. `SoundPlayer` owns short-lived playback handles while `WindowsSoundBackend` uses the built-in Windows MCI service for asynchronous WAV and MP3 playback. This keeps codec work outside the GSI and COM workers and avoids shipping QtMultimedia.

`MediaSessionMonitor` polls Windows media metadata at low frequency and emits only when the current track identity changes. Thumbnail bytes are capped, sampled once, and cached by artwork hash. The generated accent is applied to Material-inspired color roles while semantic danger, warning, and success colors remain fixed.

The frameless `TitleBar`, window controls, profile cards, sliders, progress indicators, artwork surface, interaction cursors, palette generation, and stylesheet assembly are reusable components. The title bar asks Qt to start the platform-native move operation and enables its manual fallback only when the platform declines, preventing competing drag calculations.

Every page lives under `ui_pages/`. `MainWindow` owns a small route registry that adds a page and its navigation button together, so future pages do not require scattered numeric indexes. Product and repository metadata are centralized in `app_metadata.py`, and trusted browser launches are centralized in `external_links.py`. Disabled or unavailable Windows media APIs fail closed without affecting GSI or volume control.

## Configuration safety

`ProfileStore` writes JSON to a temporary file and replaces the destination atomically. Audio profiles and kill-streak profiles live in separate directories and have separate active IDs. Pre-0.2.3 embedded kill-streak fields are migrated once and removed from audio-profile JSON. Persisted values are normalized:

- Volumes: 0–100
- Fade duration: 0–3 seconds
- State-sound maps: fixed supported state keys
- Kill-streak maps: exactly steps one through five
- Listener port: 1024–65535
- Appearance mode and seed validation
- Surface darkness, contrast, radius, and aura bounds

## Packaging

PyInstaller uses `onedir` mode. Compared with a single-file executable, it starts faster, avoids extraction at every launch, and makes antivirus false positives and missing-plugin diagnosis easier. Inno Setup installs the directory to the current user's Local AppData without requiring administrator privileges.
