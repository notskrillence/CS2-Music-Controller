# Security

## Reporting

Report security issues privately to the repository owner before publishing details.

## Local listener

The application binds its GSI endpoint to `127.0.0.1`, accepts POST payloads only with the per-install token, limits request size, and does not enable cross-origin browser access.

## Sound files

Version 0.1 accepts local WAV files. It does not upload them or execute content from them.
