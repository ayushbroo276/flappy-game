# Modi Flappy

![Modi Flappy cover](death_4.jpg)

A portrait arcade game for Android, desktop, and the web. Guide your bird through the pipes, collect coins, unlock characters with different perks, and try to beat your best score.

## Play

- **Android:** [Download the latest APK from GitHub Releases](https://github.com/ayushbroo276/flappy-game/releases/tag/android-latest). Install the APK on an Android phone. The current build is for 64-bit ARM devices and supports Android 7.0 and later.
- **Web:** [Play Modi Flappy in your browser](https://ayushbroo276.github.io/flappy-game/).
- **Desktop:** Run the game locally using the instructions below.

## Controls

- Tap or click, or press **Space** / **Up**, to flap.
- Press **Esc** or the Android **Back** button to return to the menu.
- In the shop, scroll to browse characters.

## Features

- Portrait gameplay that adapts to a phone's display.
- Coins to collect during a run, plus play-time rewards.
- A character shop with distinct perks: wider gaps, slower falling, a coin magnet, or double coins.
- Shield power-ups, achievements, saved progress, and a personal best score.
- Increasing challenge and RAGE MODE as your score grows.
- Music, sound effects, and randomized game-over messages.

## Run on desktop

Requires Python and the packages listed in [`requirements.txt`](requirements.txt).

```bash
python -m pip install -r requirements.txt
python main.py
```

## Build

The repository includes GitHub Actions workflows for the Android APK and browser version. Push to `main` to build the Android APK and publish it to the [`android-latest` GitHub Release](https://github.com/ayushbroo276/flappy-game/releases/tag/android-latest); the web workflow deploys the browser build to GitHub Pages.

To build the Android debug APK locally, install [Buildozer](https://buildozer.readthedocs.io/) and its Android build dependencies, then run:

```bash
buildozer android debug
```

The Android packaging settings are in [`buildozer.spec`](buildozer.spec).
