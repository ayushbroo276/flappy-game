# Modi Flappy

A portrait arcade game with separate Android and PC game versions. Guide your bird through the pipes, collect coins, unlock characters with different perks, and try to beat your best score.

## Play

- **Android:** [Download the latest APK from GitHub Releases](https://github.com/ayushbroo276/flappy-game/releases/tag/android-latest). Install the APK on an Android phone. The current build is for 64-bit ARM devices and supports Android 7.0 and later.
- **Web:** [Play Modi Flappy in your browser](https://ayushbroo276.github.io/flappy-game/).
- **PC:** Run the standalone PC version locally using the instructions below.

## Controls

- Tap or click, or press **Space** / **Up**, to flap.
- On Android, tap the on-screen **Menu** button or press the phone's **Back** button to return to the menu. Android buttons have forgiving touch targets.
- On PC, press **Esc** to return to the menu.
- In the shop, scroll to browse characters.

## Features

- Android gameplay fills the phone's portrait display.
- Coins to collect during a run, plus play-time rewards.
- A character shop with distinct perks: wider gaps, slower falling, a coin magnet, or double coins.
- Shield power-ups, achievements, saved progress, and a personal best score.
- Increasing challenge and RAGE MODE as your score grows.
- Music, sound effects, and randomized game-over messages.

## Run the PC version

Requires Python and the packages listed in [`requirements.txt`](requirements.txt).

```bash
python -m pip install -r requirements.txt
python flappy.py
```

## Build

The Android game is packaged from `main.py`; the separate PC game runs from `flappy.py`. GitHub Actions builds the Android APK and publishes it to the [`android-latest` GitHub Release](https://github.com/ayushbroo276/flappy-game/releases/tag/android-latest). The browser version is also built from `main.py` and deployed to GitHub Pages.

To build the Android debug APK locally, install [Buildozer](https://buildozer.readthedocs.io/) and its Android build dependencies, then run:

```bash
buildozer android debug
```

The Android packaging settings are in [`buildozer.spec`](buildozer.spec).
