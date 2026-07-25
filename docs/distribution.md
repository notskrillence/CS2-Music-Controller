# Distribution and launch checklist

## Repository presentation

1. Keep `docs/images/banner.jpg` at the top of the README.
2. Upload `docs/images/social-preview.jpg` in **Repository Settings → General → Social preview**.
3. Add the topics `counter-strike-2`, `cs2`, `audio`, `windows`, `game-state-integration`, and `open-source`.
4. Put the direct installer download in the first screen of the README once a tested release exists.
5. Include one clean application screenshot and one short demonstration GIF below the feature summary.

## Release checklist

1. Build and smoke-test the installer on a clean Windows account.
2. Create a version tag and GitHub Release.
3. Attach the installer and a SHA-256 checksum file.
4. Write release notes with three sections: what it does, what changed, and known limitations.
5. Link to the source, privacy/security explanation, and issue tracker.

## Initial launch content

Publish five short demonstrations over seven to ten days instead of posting the same announcement everywhere at once.

1. **Music gets quieter exactly when the round goes live.** Show menu, buy time, live play, and round end in under 20 seconds.
2. **CS2 kill sounds without modifying the game.** Demonstrate VALORANT, Reaver, and Tones switching.
3. **One-click profiles.** Switch between Competitive, Casual, and a personal profile while the values visibly change.
4. **Album-aware UI.** Change songs and show the restrained accent-color transition.
5. **Install in under a minute.** Show automatic cfg detection, first connection, and the working status page.

Use original footage and wording. Start with the result, show proof immediately, then identify the project and provide the GitHub call to action.

## Channel order

1. GitHub Release and README
2. A small Discord support/beta group
3. YouTube Shorts, TikTok, and Instagram Reels using the same original capture with platform-specific captions
4. Relevant Counter-Strike communities where self-promotion is allowed
5. WinGet after the installer, versioning, and update behavior are stable

Do not lead with a feature list. Lead with one visible problem and its immediate result. Reply to every useful bug report, turn repeated questions into README sections, and publish fixes quickly during the first two weeks.

## Measurements

Track only a few useful numbers for the first release:

- Release-page views
- Installer downloads
- Successful first connections
- Discord joins
- Open issues and resolved issues
- Returning users or profile saves, if local anonymous measurement is added later with explicit consent

The first goal is 25 real users who successfully install and use the application. Their problems are more valuable than a large number of low-intent video views.
