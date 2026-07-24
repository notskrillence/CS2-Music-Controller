<div align="center">
  <img src="assets/app.png" width="112" alt="CS2 Music Controller icon">
  <h1>CS2 Music Controller</h1>
  <p><strong>Native Windows music control and custom event sounds for Counter-Strike 2.</strong></p>
  <p>
    <a href="#features">Features</a> ·
    <a href="#installation">Installation</a> ·
    <a href="#how-it-works">How it works</a> ·
    <a href="#development">Development</a>
  </p>
</div>

## Status

This repository contains the first native desktop release foundation. It focuses on one job: making CS2 game-event audio easy to install, configure, and use.

- Native PySide6 desktop interface with an integrated frameless title bar
- Windows per-process audio control
- Automatic CS2 cfg discovery
- Game State Integration setup and repair
- One-click profiles, presets, and Ctrl+1 through Ctrl+5 switching
- Custom WAV event sounds
- Five-step kill-streak sequences
- Near-AMOLED Material-inspired themes with optional album-derived accents
- Localhost-only authenticated listener

## Features

### Automatic CS2 setup

On first launch, the application searches Steam registry locations, standard Steam folders, and every path in `libraryfolders.vdf`. When it finds CS2, it installs its Game State Integration configuration automatically. When detection fails, the user is asked to select:

```text
...\Counter-Strike Global Offensive\game\csgo\cfg
```

The generated integration sends only the data used by the application to `127.0.0.1` and includes a unique local token.

### Context-aware music levels

Set a separate music volume for:

| State | Behavior |
|---|---|
| Menu | Full-volume browsing and inventory time |
| In Game | Lower music during live play |
| Buy Time | Raise music during freeze/buy phase |
| Spectating | Restore music after elimination or while observing |
| Bomb Planted | Dedicated pressure-state volume |
| Round Over | Post-round transition volume |
| Warmup | Separate pre-match level |

Volume changes run on a coalescing background worker, so rapid GSI updates do not block the listener or interface.

### Custom event sounds

Each supported state can play an optional WAV file when the state begins. State sounds have their own enable switch and volume control.

### Kill-streak sequences

Assign a different WAV to kills one through five. The sequence uses CS2's round-kill value and resets when the map round changes. A lightweight default five-tone sequence is bundled so the feature works immediately.

### Profiles and presets

Profiles store the complete configuration:

- State volumes
- Fade duration
- Target media process
- State transition sounds
- Kill-streak sounds
- Sound volumes and enable switches

Bundled presets provide three starting points: **Balanced**, **Focus**, and **Cinematic**. Profiles switch immediately from the integrated title bar or one-click cards. They can also be created, renamed, duplicated, imported, exported, and deleted. The first five profiles are available through `Ctrl+1` to `Ctrl+5`.

### Appearance and album-aware color

The interface uses a near-AMOLED surface hierarchy and one coordinated accent role instead of unrelated per-state colors. Appearance modes include:

- **Album dynamic** — samples Windows media artwork once per track, caches the result, and uses it for selection and emphasis
- **CS2MC dark** — stable branded dark palette
- **Custom seed** — user-selected accent with contrast, surface darkness, radius, aura, and motion controls

Bomb, warning, success, and error colors remain semantic and do not change with album artwork. Essential fonts and interface assets are local; the application does not depend on an internet font request.

### Music target selection

Use the active Windows media player automatically, or pin a specific process such as Spotify, YouTube Music, Firefox, or foobar2000. Active Windows audio sessions are highlighted in the selector.

## Installation

### Run from source

Requirements:

- Windows 10 or Windows 11
- Python 3.11+

Double-click:

```text
run_dev.bat
```

The script creates `.venv`, installs dependencies, and launches the native application.

### Build the Windows installer

1. Install Python 3.11 and Inno Setup 6.
2. Open PowerShell in the repository.
3. Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_release.ps1
```

The build uses PyInstaller's `onedir` mode for faster startup and simpler diagnosis. The final installer is written to:

```text
installer\output\CS2MusicController-Setup-0.2.0.exe
```

When Inno Setup is unavailable, the portable build remains in `dist\CS2MusicController`.

## How it works

```text
CS2 GSI POST
    │
    ▼
Authenticated 127.0.0.1 listener
    │
    ▼
State resolver ───────────────► Native dashboard
    │                              │
    ├── state transition           └── QSoundEffect WAV playback
    │
    └── coalesced volume command
             │
             ▼
      Windows audio session
```

The program does not inject into CS2, read process memory, inspect packets, draw a game overlay, or expose a network service. It consumes Valve's Game State Integration payloads and adjusts a Windows audio session.

More detail: [Architecture](docs/architecture.md)

## Data and configuration

Application data is stored in:

```text
%APPDATA%\CS2MusicController
```

Contents:

```text
settings.json       Active profile, CS2 path, listener token, port, and appearance roles
profiles\*.json     User profiles
```

The CS2 integration file is:

```text
gamestate_integration_cs2_music_controller.cfg
```

Deleting that file disconnects CS2 from the application. The Setup page can reinstall or repair it.

## Development

Install development dependencies and run tests:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q
```

For interface demonstrations without launching CS2, start the application and send a synthetic state:

```powershell
python tools\send_test_gsi.py bomb_planted --kills 3
```

Current tests cover:

- Required CS2 state classification
- Kill-streak increment and round reset behavior
- Rejection of non-CS2 payloads
- Steam library VDF parsing
- Local tokenized GSI generation
- Profile creation, rename, persistence, switching, and deletion
- Appearance migration, normalization, and persistence
- Dynamic accent generation with neutral AMOLED surfaces

## Project structure

```text
app.py                         Application entry point
src/cs2mc/gui.py               Native pages, shell, and onboarding
src/cs2mc/ui_components.py     Title bar and reusable profile components
src/cs2mc/theme.py             Material-inspired role palette and stylesheet
src/cs2mc/media_session.py     Track metadata and album artwork monitor
src/cs2mc/runtime.py           Runtime coordination
src/cs2mc/state_engine.py      GSI state and kill resolver
src/cs2mc/gsi_server.py        Authenticated local listener
src/cs2mc/audio_controller.py  Background Windows volume control
src/cs2mc/cs2_locator.py       Steam/CS2 discovery and GSI installer
src/cs2mc/config.py            Atomic settings and profile storage
src/cs2mc/sound_player.py      Low-latency WAV playback
installer/                     Inno Setup definition
```

## Contributing

Bug reports and focused pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a change.

## License

MIT. See [LICENSE](LICENSE).
