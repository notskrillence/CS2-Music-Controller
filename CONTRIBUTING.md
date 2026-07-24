# Contributing

## Scope

Keep changes aligned with the current product promise: reliable CS2 music control, custom event sounds, kill-streak sequences, profiles, installation, and release quality.

Changes involving account systems, payments, matchmaking automation, live tactical overlays, process injection, memory reading, or hidden competitive information are outside this repository's current scope.

## Development workflow

1. Create a focused branch.
2. Add or update tests for behavior changes.
3. Run `pytest -q`.
4. Test the native interface on Windows 10 or 11 with CS2 and at least one supported media player.
5. Keep pull requests small enough to review directly.

## Code principles

- Keep network handlers non-blocking.
- Keep COM calls off the GUI thread.
- Prefer built-in Windows and Qt capabilities before adding dependencies.
- Keep configuration migrations backward compatible.
- Do not commit user profiles, tokens, absolute machine paths, or copyrighted sound packs.
