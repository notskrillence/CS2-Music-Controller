# Architecture

## Design goals

1. Keep the GSI request path short and non-blocking.
2. Keep Windows COM and audio operations off the Qt interface thread.
3. Persist configuration atomically so a crash cannot leave half-written JSON.
4. Treat the CS2 installation path and generated GSI file as repairable setup state.
5. Keep the native interface independent from the local HTTP transport.
6. Apply theme changes only on user input or track changes; never run a permanent animation or palette loop.
7. Keep reusable shell, theme, media, and profile components outside the page implementation.

## Runtime flow

`GSIServer` binds only to `127.0.0.1`. Its handler validates the per-install token and passes decoded JSON to `RuntimeController`.

`GameStateResolver` reduces payloads into one stable state and detects increases in `player.state.round_kills`. It resets the stored kill count when `map.round` changes.

`RuntimeController` takes a thread-safe profile snapshot. State changes enqueue one volume command and optionally request a state sound. Kill increases request the configured streak sound.

`MediaVolumeController` owns a dedicated COM thread. It keeps only the newest pending command and interrupts a fade when a newer command arrives. This prevents a queue of obsolete volume transitions during rapid state changes.

Qt signals carry snapshots, logs, audio-session lists, media metadata, and sound requests back to the interface thread. `QSoundEffect` handles WAV playback without blocking the GSI or COM workers.

`MediaSessionMonitor` polls Windows media metadata at low frequency and emits only when the current track identity changes. Thumbnail bytes are capped, sampled once, and cached by artwork hash. The generated accent is applied to Material-inspired color roles while semantic danger, warning, and success colors remain fixed.

The frameless `TitleBar`, profile cards, interaction cursors, palette generation, and stylesheet assembly are separate reusable modules. Disabled or unavailable Windows media APIs fail closed without affecting GSI or volume control.

## Configuration safety

`ProfileStore` writes JSON to a temporary file and replaces the destination atomically. Profiles are normalized before persistence:

- Volumes: 0–100
- Fade duration: 0–3 seconds
- Sound maps: fixed supported keys
- Listener port: 1024–65535
- Appearance mode and seed validation
- Surface darkness, contrast, radius, and aura bounds

## Packaging

PyInstaller uses `onedir` mode. Compared with a single-file executable, it starts faster, avoids extraction at every launch, and makes antivirus false positives and missing-plugin diagnosis easier. Inno Setup installs the directory to the current user's Local AppData without requiring administrator privileges.
