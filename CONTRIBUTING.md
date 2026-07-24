# Contributing

## Scope

Keep changes aligned with the current product promise: reliable CS2 music control, custom event sounds, kill-streak sequences, profiles, installation, and release quality.

Changes involving account systems, payments, matchmaking automation, live tactical overlays, process injection, memory reading, or hidden competitive information are outside this repository's current scope.

## Development workflow

1. Run `setup_dev.bat` once to create the environment and install development dependencies.
2. Create a focused branch.
3. Add or update tests for behavior changes.
4. Run `.\.venv\Scripts\python.exe -m pytest -q`.
5. Test the native interface on Windows 10 or 11 with CS2 and at least one supported media player.
6. Keep pull requests small enough to review directly.

## Code principles

- Keep network handlers non-blocking.
- Keep COM calls off the GUI thread.
- Prefer built-in Windows and Qt capabilities before adding dependencies.
- Keep configuration migrations backward compatible.
- Do not commit user profiles, tokens, absolute machine paths, or copyrighted sound packs.
