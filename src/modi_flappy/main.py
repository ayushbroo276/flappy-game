"""
Flappy game - ANDROID + WEB + DESKTOP version (pygame / buildozer / pygbag)

Features
  * Menu, Resume, Settings, Shop, Achievements
  * Coins to collect between the pipes + coins for every minute you play
  * Shield power-up (survives one hit)
  * Characters that play differently (see "perk" lines in CHARACTERS)
  * Funny random death messages
  * Share button (share sheet on phones, saved score card on desktop)
  * Speed-up and RAGE MODE as your score grows
  * Fair, smooth collisions: you only die when you really touch a pipe or the ground

Game art belongs in assets/images and music and sound effects belong in
assets/audio. Web builds use .ogg music files.
Optional sound files (otherwise built-in beeps are used):
    flap.wav, point.wav, coin.wav, powerup.wav, shield_break.wav

Controls: SPACE / UP / click / tap = flap.   ESC = pause / back to the menu.
"""
import asyncio
import json
import math
import os
import random
import sys
from array import array

import pygame

from .paths import asset_path, project_root

WEB = sys.platform == "emscripten"
if WEB:
    import platform  # pygbag's platform module gives access to the browser

ANDROID = "ANDROID_ARGUMENT" in os.environ   # python-for-android sets this
if ANDROID:
    # keep the phone's Back button inside our game instead of closing the app
    os.environ.setdefault("SDL_ANDROID_TRAP_BACK_BUTTON", "1")

# Keys / events that mean "go back" or "app went to the background"
BACK_KEYS = (pygame.K_ESCAPE, getattr(pygame, "K_AC_BACK", pygame.K_ESCAPE))
APP_BACKGROUND_EVENT = getattr(pygame, "APP_WILLENTERBACKGROUND", -1)

# ---------- Settings you can change ----------
DEATH_SOUND_FILE = "death.wav"
SAVE_FILE = "save.json"
SAVE_KEY = "flappy_save"   # name used for saving inside the browser
GAME_URL = ""              # put your itch.io link here after publishing (used by Share)

# Funny messages shown at random when you die, each with its own picture that
# appears ABOVE the message. Format: ("message", "picture file").
# Put the pictures in the same folder. If a picture is missing, that message is
# simply shown without one. (Add or remove lines as you like.)
DEATH_MESSAGES = [
    ("Hug diya", "death_.jpg"),
    ("Ja re", "death_1.jpg"),
    ("Ale le le le", "death_2.jpg"),
    ("Really tried to overtake a flying pigeon. Kabootar wins!", "death_3.jpg"),
    ("Rahu-Ketu heavy chal rahe hain aapke.", "death_4.jpg"),
]

# Characters in the shop. The first one is free and owned from the start,
# and its song/background are used whenever another character's are missing.
# Perks (all optional):
#   gap_bonus     - pixels added to the gap between pipes
#   gravity_mult  - below 1.0 = falls slower
#   magnet        - radius (pixels) that pulls coins toward you
#   coin_mult     - multiplies the value of every coin you pick up
CHARACTERS = [
    {"name": "Classic", "file": "bird.jpg", "price": 0, "color": (255, 220, 0),
     "music": "music.ogg", "background": "background.jpg",
     "perk": "Balanced bird"},
    {"name": "Red", "file": "bird_red.jpg", "price": 30, "color": (230, 70, 70),
     "music": "music_red.ogg", "background": "background_red.jpg",
     "perk": "Wider gaps between pipes", "gap_bonus": 30},
    {"name": "Blue", "file": "bird_blue.jpg", "price": 50, "color": (70, 130, 240),
     "music": "music_blue.ogg", "background": "background_blue.jpg",
     "perk": "Floaty: falls slower", "gravity_mult": 0.8},
    {"name": "Green", "file": "bird_green.jpg", "price": 80, "color": (60, 190, 90),
     "music": "music_green.ogg", "background": "background_green.jpg",
     "perk": "Coin magnet", "magnet": 110},
    {"name": "Purple", "file": "bird_purple.jpg", "price": 120, "color": (160, 90, 220),
     "music": "music_purple.ogg", "background": "background_purple.jpg",
     "perk": "Double coins", "coin_mult": 2},
]

# Achievements: (id, name, description)
ACHIEVEMENTS = [
    ("first_flight", "First Flight", "Score 1 point"),
    ("pipe_dodger", "Pipe Dodger", "Score 10 in one run"),
    ("pipe_legend", "Pipe Legend", "Score 25 in one run"),
    ("coin_collector", "Coin Collector", "Pick up 50 coins from pipes"),
    ("close_call", "Close Call", "Survive a hit with a shield"),
    ("fashion_bird", "Fashion Bird", "Own every character"),
]
ACH_NAMES = {key: name for key, name, _ in ACHIEVEMENTS}

COINS_PER_REWARD = 10        # coins you get...
MS_PER_REWARD = 60000        # ...for every 60,000 ms (1 minute) of play
RESUME_COUNTDOWN_MS = 3000   # 3 second countdown after pressing Resume
RAGE_SCORE = 15              # RAGE MODE starts at this score

GAME_TITLE = "Modi Flappy"
WIDTH = 400
BASE_HEIGHT = 600
FPS = 60

pygame.mixer.pre_init(44100, -16, 2, 1024 if ANDROID else 512)
pygame.init()

if ANDROID:
    try:
        from jnius import autoclass

        View = autoclass("android.view.View")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        decor_view = PythonActivity.mActivity.getWindow().getDecorView()
        immersive_flags = (
            View.SYSTEM_UI_FLAG_FULLSCREEN
            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
        )
        decor_view.setSystemUiVisibility(immersive_flags)
    except Exception as exc:
        print(f"Could not hide the Android system bars: {exc}")

    display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    DISPLAY_WIDTH, DISPLAY_HEIGHT = display.get_size()
    if DISPLAY_WIDTH <= 0 or DISPLAY_HEIGHT <= 0:
        raise RuntimeError(f"Android returned an invalid display size: {display.get_size()}")
    HEIGHT = max(BASE_HEIGHT, round(WIDTH * DISPLAY_HEIGHT / DISPLAY_WIDTH))
    screen = pygame.Surface((WIDTH, HEIGHT))
else:
    HEIGHT = BASE_HEIGHT
    display = pygame.display.set_mode((WIDTH, HEIGHT))
    DISPLAY_WIDTH, DISPLAY_HEIGHT = display.get_size()
    screen = display


def ui_y(y):
    return round(y * HEIGHT / BASE_HEIGHT)


def game_position(position):
    if not ANDROID:
        return position
    return (
        round(position[0] * WIDTH / DISPLAY_WIDTH),
        round(position[1] * HEIGHT / DISPLAY_HEIGHT),
    )


# Physics (pixels and seconds, so it feels the same on every screen/phone)
GRAVITY = 1620.0
FLAP_POWER = -480.0
MAX_FALL = 720.0
PIPE_SPEED = 180.0
PIPE_GAP = 175
PIPE_WIDTH = 70
PIPE_SPACING = 230       # distance between pipes
MAX_GAP_SHIFT = 190      # how far the next gap can move up/down (keeps it fair)
PIPE_CAP_H = 22

GROUND_H = 40
GROUND_Y = HEIGHT - GROUND_H
BIRD_X = 90
BIRD_SIZE = (50, 50)
HIT_RADIUS = 19          # the bird's hit-circle (a bit smaller than the picture)
ITEM_RADIUS = 14
# ---------------------------------------------

if WEB:
    BASE_DIR = ""
else:
    BASE_DIR = project_root()


if ANDROID:
    # app data folder that survives app updates (the app folder itself does not)
    SAVE_DIR = os.environ.get("ANDROID_PRIVATE", BASE_DIR)
else:
    SAVE_DIR = BASE_DIR


def file_path(name):
    return asset_path(name, BASE_DIR)


def save_path():
    return os.path.join(SAVE_DIR, SAVE_FILE)


pygame.display.set_caption(GAME_TITLE)
clock = pygame.time.Clock()
# Font(None, size) uses pygame's built-in font, which works in the browser too
title_font = pygame.font.Font(None, 64)
font = pygame.font.Font(None, 48)
button_font = pygame.font.Font(None, 34)
small_font = pygame.font.Font(None, 28)
tiny_font = pygame.font.Font(None, 22)
msg_font = pygame.font.Font(None, 30)

# ---------------- Save data ----------------
DEFAULT_SAVE = {
    "coins": 0,
    "owned": [CHARACTERS[0]["name"]],
    "selected": CHARACTERS[0]["name"],
    "music_vol": 0.5,
    "sfx_vol": 1.0,
    "play_ms": 0,
    "best": 0,
    "pipe_coins": 0,
    "achievements": [],
}
char_by_name = {c["name"]: c for c in CHARACTERS}


def load_save():
    data = dict(DEFAULT_SAVE)
    data["owned"] = list(DEFAULT_SAVE["owned"])
    data["achievements"] = []
    try:
        if WEB:
            raw = platform.window.localStorage.getItem(SAVE_KEY)
            if raw:
                data.update(json.loads(str(raw)))
        else:
            with open(save_path(), "r", encoding="utf-8") as f:
                data.update(json.load(f))
    except Exception:
        pass
    # Make sure the data is sane
    first = CHARACTERS[0]["name"]
    if not isinstance(data["owned"], list):
        data["owned"] = [first]
    data["owned"] = [n for n in data["owned"] if n in char_by_name]
    if first not in data["owned"]:
        data["owned"].append(first)
    if data["selected"] not in data["owned"]:
        data["selected"] = first
    if not isinstance(data["achievements"], list):
        data["achievements"] = []
    return data


def write_save():
    try:
        if WEB:
            platform.window.localStorage.setItem(SAVE_KEY, json.dumps(save))
        else:
            with open(save_path(), "w", encoding="utf-8") as f:
                json.dump(save, f)
    except Exception:
        print("Could not write save data.")


save = load_save()

# ---------------- Images ----------------


def scale_image(img, size):
    try:
        return pygame.transform.smoothscale(img, size)
    except (ValueError, pygame.error):
        return pygame.transform.scale(img, size)


def make_placeholder(size, color):
    surf = pygame.Surface(size, pygame.SRCALPHA)
    w, h = size
    pygame.draw.ellipse(surf, color, surf.get_rect())
    pygame.draw.circle(surf, (255, 255, 255), (int(w * 0.68), int(h * 0.35)), max(3, h // 6))
    pygame.draw.circle(surf, (0, 0, 0), (int(w * 0.72), int(h * 0.35)), max(2, h // 12))
    pygame.draw.polygon(
        surf, (255, 140, 0),
        [(int(w * 0.85), int(h * 0.5)), (w, int(h * 0.58)), (int(w * 0.85), int(h * 0.66))],
    )
    return surf


def load_character_image(char, size):
    try:
        img = pygame.image.load(file_path(char["file"])).convert_alpha()
        return scale_image(img, size)
    except (pygame.error, FileNotFoundError):
        return make_placeholder(size, char["color"])


def load_background(file_name):
    """Returns a background Surface, or None if the file can't be loaded."""
    try:
        img = pygame.image.load(file_path(file_name)).convert()
        return scale_image(img, (WIDTH, HEIGHT))
    except (pygame.error, FileNotFoundError):
        return None


def find_music(file_name):
    """Finds the song file. Supports .ogg, .mp3, and .wav across web and mobile."""
    stem, _ = os.path.splitext(file_name)
    extensions = (".ogg", ".mp3", ".wav")
    for ext in extensions:
        path = file_path(stem + ext)
        if os.path.exists(path):
            return path
    return None


for c in CHARACTERS:
    for key in ("file", "background"):
        if not os.path.exists(file_path(c[key])):
            print(f"{c[key]} not found ({c['name']} {key}); using a fallback.")
    if find_music(c["music"]) is None:
        print(f"{c['music']} not found ({c['name']} music); using a fallback.")

def find_image(file_name):
    """Finds an image even if you saved it as .png / .jpg / .jpeg by mistake."""
    if os.path.exists(file_path(file_name)):
        return file_path(file_name)
    stem, _ = os.path.splitext(file_name)
    for ext in (".png", ".jpg", ".jpeg"):
        path = file_path(stem + ext)
        if os.path.exists(path):
            return path
    return None


DEATH_IMG_BOX = (150, 110)   # biggest size of the picture above the message


def load_death_image(file_name):
    path = find_image(file_name)
    if not path:
        print(f"{file_name} not found; that death message will have no picture.")
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
        w, h = img.get_size()
        factor = min(DEATH_IMG_BOX[0] / w, DEATH_IMG_BOX[1] / h)
        return scale_image(img, (max(1, int(w * factor)), max(1, int(h * factor))))
    except pygame.error:
        return None


death_images = {img_file: load_death_image(img_file) for _, img_file in DEATH_MESSAGES}

char_imgs = {c["name"]: load_character_image(c, BIRD_SIZE) for c in CHARACTERS}
char_previews = {c["name"]: load_character_image(c, (44, 44)) for c in CHARACTERS}

# Backgrounds: each character's own, falling back to Classic's, then a plain color
default_bg = load_background(CHARACTERS[0]["background"])
if default_bg is None:
    default_bg = pygame.Surface((WIDTH, HEIGHT))
    default_bg.fill((110, 190, 255))
bg_imgs = {}
for c in CHARACTERS:
    bg_imgs[c["name"]] = load_background(c["background"]) or default_bg


def current_bg():
    return bg_imgs[save["selected"]]


overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
overlay.fill((0, 0, 0, 150))
rage_surface = pygame.Surface((WIDTH, HEIGHT))
rage_surface.fill((255, 0, 0))
shield_surface = pygame.Surface((HIT_RADIUS * 2 + 36, HIT_RADIUS * 2 + 36), pygame.SRCALPHA)
pygame.draw.circle(shield_surface, (120, 200, 255, 70), shield_surface.get_rect().center, HIT_RADIUS + 16)
pygame.draw.circle(shield_surface, (160, 220, 255, 220), shield_surface.get_rect().center, HIT_RADIUS + 16, 3)
death_panel = pygame.Surface((340, 450), pygame.SRCALPHA)
pygame.draw.rect(death_panel, (0, 0, 0, 175), death_panel.get_rect(), border_radius=18)
pygame.draw.rect(death_panel, (255, 255, 255, 220), death_panel.get_rect(), 2, border_radius=18)

# ---------------- Sounds ----------------


def make_tone(freq, ms, vol=0.3, slide=0.0):
    """Builds a short beep so the game has sound effects without any files."""
    try:
        init = pygame.mixer.get_init()
        if not init:
            return None
        rate, fmt, channels = init
        if fmt != -16:
            return None
        n = max(1, int(rate * ms / 1000))
        buf = array("h")
        phase = 0.0
        for i in range(n):
            f = freq + slide * (i / n)
            phase += 2 * math.pi * f / rate
            envelope = 1.0 - i / n
            value = int(32767 * vol * envelope * math.sin(phase))
            for _ in range(channels):
                buf.append(value)
        return pygame.mixer.Sound(buffer=buf.tobytes())
    except Exception:
        return None


SFX_FILES = {
    "flap": "flap.wav", "point": "point.wav", "coin": "coin.wav",
    "powerup": "powerup.wav", "shield_break": "shield_break.wav",
}


def load_sfx(name, fallback):
    path = file_path(SFX_FILES[name])
    if os.path.exists(path):
        try:
            return pygame.mixer.Sound(path)
        except pygame.error:
            pass
    return fallback


sfx = {
    "flap": load_sfx("flap", make_tone(520, 70, 0.12, 380)),
    "point": load_sfx("point", make_tone(880, 90, 0.22)),
    "coin": load_sfx("coin", make_tone(1100, 130, 0.25, 700)),
    "powerup": load_sfx("powerup", make_tone(500, 220, 0.25, 800)),
    "shield_break": load_sfx("shield_break", make_tone(320, 220, 0.3, -220)),
}

death_sound = None
try:
    death_sound = pygame.mixer.Sound(file_path(DEATH_SOUND_FILE))
except (pygame.error, FileNotFoundError):
    print(f"Could not load {DEATH_SOUND_FILE}, death will be silent.")

current_music = None  # name of the character whose song is currently loaded


def apply_volumes():
    pygame.mixer.music.set_volume(save["music_vol"])
    if death_sound:
        death_sound.set_volume(save["sfx_vol"])
    for s in sfx.values():
        if s:
            s.set_volume(save["sfx_vol"])


apply_volumes()


def play(name):
    s = sfx.get(name)
    if s:
        s.play()


def music_path_for(name):
    """The selected character's song, or Classic's song if it is missing."""
    return find_music(char_by_name[name]["music"]) or find_music(CHARACTERS[0]["music"])


def start_music():
    global current_music
    name = save["selected"]
    path = music_path_for(name)
    if not path:
        return
    try:
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(save["music_vol"])
        pygame.mixer.music.play(-1)  # -1 = loop forever
        current_music = name
    except pygame.error:
        print(f"Could not play {path}. Try converting it to .ogg.")


def stop_music():
    pygame.mixer.music.stop()


# ---------------- Game state ----------------
scene = "menu"        # "menu", "settings", "shop", "achievements", "game"
game = None           # None = no game yet
shop_scroll = 0
buttons = []          # filled every frame by button()
toasts = []           # small pop-up messages: [text, ms_left]
last_death_msg = ""

LIST_AREA = pygame.Rect(10, ui_y(85), 380, ui_y(500) - ui_y(85))
ROW_H = 76
ROW_PITCH = 82


def perk(key, default=0):
    return char_by_name[save["selected"]].get(key, default)


def show_toast(text, ms=2200):
    if len(toasts) < 4:
        toasts.append([text, ms])


def update_toasts(dt_ms):
    if toasts:
        toasts[0][1] -= dt_ms
        if toasts[0][1] <= 0:
            toasts.pop(0)


def unlock(key):
    if key in save["achievements"]:
        return
    save["achievements"].append(key)
    write_save()
    show_toast("Achievement: " + ACH_NAMES[key], 2600)
    play("coin")


def new_game():
    return {
        "x": float(BIRD_X), "y": HEIGHT // 2 - 20.0, "vel": 0.0, "spin": 0.0,
        "pipes": [], "items": [], "particles": [],
        "score": 0, "run_coins": 0,
        "phase": "ready",      # "ready" -> "playing" -> "dead"
        "countdown": 0, "dead_ms": 0, "settled": False,
        "t": 0.0, "scroll": 0.0,
        "shield": False, "invuln_ms": 0,
        "flap_ms": 0, "shake_ms": 0,
        "banner": "", "banner_ms": 0,
        "death_msg": "", "last_gap_y": HEIGHT // 2,
    }


def pick_death_message():
    """Returns (text, picture_file) - never the same one twice in a row."""
    global last_death_msg
    options = [m for m in DEATH_MESSAGES if m[0] != last_death_msg] or DEATH_MESSAGES
    choice = random.choice(options)
    last_death_msg = choice[0]
    return choice


def spawn_pipe(g):
    gap = PIPE_GAP + perk("gap_bonus", 0)
    margin = 90
    lo = margin + gap // 2
    hi = GROUND_Y - margin - gap // 2
    prev = g["last_gap_y"]
    lo2 = max(lo, prev - MAX_GAP_SHIFT)
    hi2 = min(hi, prev + MAX_GAP_SHIFT)
    if lo2 > hi2:
        lo2, hi2 = lo, hi
    gap_y = random.randint(int(lo2), int(hi2))
    g["last_gap_y"] = gap_y
    x = WIDTH + 10
    g["pipes"].append({"x": float(x), "gap_y": gap_y, "gap": gap, "passed": False})

    roll = random.random()
    item_y = gap_y + random.randint(-gap // 4, gap // 4)
    item_x = x + PIPE_WIDTH / 2
    if roll < 0.08 and not g["shield"]:
        g["items"].append({"type": "shield", "x": item_x, "y": float(item_y)})
    elif roll < 0.70:
        g["items"].append({"type": "coin", "x": item_x, "y": float(item_y)})


def pipe_parts(pipe):
    """Rectangles that make up a pipe pair. Used for BOTH drawing and collisions,
    so you only die when you really touch something you can see."""
    x = int(round(pipe["x"]))
    top_h = int(pipe["gap_y"] - pipe["gap"] / 2)
    bottom_y = int(pipe["gap_y"] + pipe["gap"] / 2)
    top = pygame.Rect(x, 0, PIPE_WIDTH, top_h)
    bottom = pygame.Rect(x, bottom_y, PIPE_WIDTH, GROUND_Y - bottom_y)
    top_cap = pygame.Rect(x - 4, top_h - PIPE_CAP_H, PIPE_WIDTH + 8, PIPE_CAP_H)
    bottom_cap = pygame.Rect(x - 4, bottom_y, PIPE_WIDTH + 8, PIPE_CAP_H)
    return [top, bottom, top_cap, bottom_cap]


def circle_hits_rect(cx, cy, r, rect):
    nearest_x = max(rect.left, min(cx, rect.right))
    nearest_y = max(rect.top, min(cy, rect.bottom))
    return (cx - nearest_x) ** 2 + (cy - nearest_y) ** 2 < r * r


def current_speed(g):
    mult = 1.0 + min(0.4, 0.04 * (g["score"] // 5))
    if g["score"] >= RAGE_SCORE:
        mult += 0.1
    return PIPE_SPEED * mult


def burst(g, x, y, colors, count, speed=240):
    for _ in range(count):
        angle = random.uniform(0, math.tau)
        sp = random.uniform(40, speed)
        life = random.uniform(0.4, 0.9)
        g["particles"].append({
            "x": x, "y": y, "vx": math.cos(angle) * sp, "vy": math.sin(angle) * sp - 60,
            "life": life, "color": random.choice(colors), "r": random.randint(2, 5),
        })


def update_particles(g, dt):
    alive = []
    for p in g["particles"]:
        p["life"] -= dt
        if p["life"] > 0:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += 700 * dt
            alive.append(p)
    g["particles"] = alive


def resume_available():
    return game is not None and game["phase"] in ("ready", "playing")


# ---------------- Actions (called by buttons) ----------------
def go(name):
    global scene, shop_scroll
    scene = name
    shop_scroll = 0


def start_game():
    global game, scene
    stop_music()
    game = new_game()
    scene = "game"


def resume_game():
    global scene
    scene = "game"
    if game["phase"] == "playing":
        game["countdown"] = RESUME_COUNTDOWN_MS
        if current_music == save["selected"]:
            pygame.mixer.music.unpause()
        else:
            start_music()  # character was changed while paused: play its song


def pause_to_menu():
    global scene
    if game and game["phase"] == "playing":
        pygame.mixer.music.pause()
    write_save()
    scene = "menu"


def quit_game():
    write_save()
    pygame.quit()
    sys.exit()


def buy(name):
    char = char_by_name[name]
    if name not in save["owned"] and save["coins"] >= char["price"]:
        save["coins"] -= char["price"]
        save["owned"].append(name)
        save["selected"] = name
        write_save()
        play("powerup")
        if len(save["owned"]) == len(CHARACTERS):
            unlock("fashion_bird")


def select(name):
    if name in save["owned"]:
        save["selected"] = name
        write_save()


def change_volume(key, delta):
    save[key] = round(min(1.0, max(0.0, save[key] + delta)), 1)
    apply_volumes()
    write_save()
    if key == "sfx_vol":
        play("coin")  # preview


def share_score():
    g = game
    if not g:
        return
    text = f"I scored {g['score']} in {GAME_TITLE} as the {save['selected']} bird! Can you beat me?"
    if GAME_URL:
        text += " " + GAME_URL
    if WEB:
        try:
            js = (
                "(function(){var t=" + json.dumps(text) + ";"
                "if(navigator.share){navigator.share({text:t}).catch(function(){});}"
                "else if(navigator.clipboard){navigator.clipboard.writeText(t);}})()"
            )
            platform.window.eval(js)
            show_toast("Shared / copied to clipboard!")
        except Exception:
            show_toast("Sharing is not supported here")
    elif ANDROID:
        try:
            from jnius import autoclass  # pyjnius lets Python call Android's share sheet
            Intent = autoclass("android.content.Intent")
            String = autoclass("java.lang.String")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            intent = Intent()
            intent.setAction(Intent.ACTION_SEND)
            intent.putExtra(Intent.EXTRA_TEXT, String(text))
            intent.setType("text/plain")
            chooser = Intent.createChooser(intent, String("Share your score"))
            PythonActivity.mActivity.startActivity(chooser)
        except Exception:
            show_toast("Sharing is not available")
    else:
        try:
            pygame.image.save(screen.copy(), file_path("flappy_score.png"))
            show_toast("Score card saved: flappy_score.png", 3000)
        except Exception:
            show_toast("Could not save the score card")
        try:
            pygame.scrap.init()
            pygame.scrap.put_text(text)
        except Exception:
            pass


def flap():
    global game
    g = game
    phase = g["phase"]
    if phase == "ready":
        g["phase"] = "playing"
        g["vel"] = FLAP_POWER
        g["flap_ms"] = 140
        start_music()
        play("flap")
    elif phase == "playing":
        if g["countdown"] <= 0:
            g["vel"] = FLAP_POWER
            g["flap_ms"] = 140
            play("flap")
    elif phase == "dead" and g["dead_ms"] >= 500:
        game = new_game()
        game["phase"] = "playing"
        game["vel"] = FLAP_POWER
        game["flap_ms"] = 140
        start_music()
        play("flap")


def die(g):
    g["phase"] = "dead"
    g["dead_ms"] = 0
    g["shake_ms"] = 350
    g["vel"] = -260.0
    g["death_msg"] = pick_death_message()
    save["best"] = max(save["best"], g["score"])
    stop_music()
    if death_sound:
        death_sound.play()
    burst(g, g["x"], g["y"], [(255, 255, 255), (255, 220, 120), (255, 120, 120)], 26)
    write_save()


def update_game(dt_ms):
    g = game
    dt = dt_ms / 1000.0
    for key in ("flap_ms", "shake_ms", "banner_ms", "invuln_ms"):
        g[key] = max(0, g[key] - dt_ms)
    update_particles(g, dt)

    if g["phase"] == "ready":
        g["t"] += dt
        g["y"] = HEIGHT // 2 - 20 + 8 * math.sin(g["t"] * 4)
        return

    if g["phase"] == "dead":
        g["dead_ms"] += dt_ms
        if not g["settled"]:
            g["vel"] += GRAVITY * dt
            g["y"] += g["vel"] * dt
            g["spin"] += 540 * dt
            if g["y"] + HIT_RADIUS >= GROUND_Y:
                g["y"] = GROUND_Y - HIT_RADIUS
                g["vel"] = 0.0
                g["settled"] = True
        return

    if g["countdown"] > 0:
        g["countdown"] -= dt_ms
        return

    # Coins for play time (only counts while really playing)
    save["play_ms"] += dt_ms
    if save["play_ms"] >= MS_PER_REWARD:
        rewards = int(save["play_ms"] // MS_PER_REWARD)
        save["play_ms"] -= rewards * MS_PER_REWARD
        save["coins"] += rewards * COINS_PER_REWARD
        show_toast(f"+{rewards * COINS_PER_REWARD} coins for playing!")
        write_save()

    # Bird physics (smooth floats, time based)
    g["vel"] += GRAVITY * perk("gravity_mult", 1.0) * dt
    g["vel"] = min(g["vel"], MAX_FALL)
    g["y"] += g["vel"] * dt
    if g["y"] - HIT_RADIUS < 0:       # the ceiling never kills you
        g["y"] = HIT_RADIUS
        g["vel"] = max(g["vel"], 0.0)

    # World scrolling
    speed = current_speed(g)
    g["scroll"] += speed * dt
    if not g["pipes"] or g["pipes"][-1]["x"] < WIDTH - PIPE_SPACING:
        spawn_pipe(g)
    for pipe in g["pipes"]:
        pipe["x"] -= speed * dt
        if not pipe["passed"] and pipe["x"] + PIPE_WIDTH < g["x"]:
            pipe["passed"] = True
            g["score"] += 1
            play("point")
            score = g["score"]
            if score == 1:
                unlock("first_flight")
            if score == 10:
                unlock("pipe_dodger")
            if score == 25:
                unlock("pipe_legend")
            if score == RAGE_SCORE:
                g["banner"], g["banner_ms"] = "RAGE MODE!", 1600
            elif score % 10 == 0:
                g["banner"], g["banner_ms"] = "SPEED UP!", 1300
    g["pipes"] = [p for p in g["pipes"] if p["x"] > -PIPE_WIDTH - 10]

    # Coins and power-ups
    magnet = perk("magnet", 0)
    remaining = []
    for item in g["items"]:
        item["x"] -= speed * dt
        dx = g["x"] - item["x"]
        dy = g["y"] - item["y"]
        dist = math.hypot(dx, dy)
        if item["type"] == "coin" and magnet and 1 < dist < magnet:
            pull = 460 * dt
            item["x"] += dx / dist * pull
            item["y"] += dy / dist * pull
            dist = math.hypot(g["x"] - item["x"], g["y"] - item["y"])
        if dist < HIT_RADIUS + ITEM_RADIUS:
            if item["type"] == "coin":
                value = perk("coin_mult", 1)
                save["coins"] += value
                save["pipe_coins"] += 1
                g["run_coins"] += value
                play("coin")
                burst(g, item["x"], item["y"], [(255, 215, 0), (255, 245, 150)], 10, 160)
                if save["pipe_coins"] >= 50:
                    unlock("coin_collector")
                write_save()
            else:
                g["shield"] = True
                play("powerup")
                burst(g, item["x"], item["y"], [(120, 200, 255), (255, 255, 255)], 14, 180)
                show_toast("Shield! Survives one hit", 1800)
            continue
        if item["x"] > -30:
            remaining.append(item)
    g["items"] = remaining

    # Collisions: only real contact with a pipe or the ground counts
    hit_pipe = False
    for pipe in g["pipes"]:
        if pipe["x"] > g["x"] + HIT_RADIUS + 12 or pipe["x"] + PIPE_WIDTH + 12 < g["x"] - HIT_RADIUS:
            continue
        for rect in pipe_parts(pipe):
            if circle_hits_rect(g["x"], g["y"], HIT_RADIUS, rect):
                hit_pipe = True
                break
    hit_ground = g["y"] + HIT_RADIUS >= GROUND_Y
    if hit_ground:
        g["y"] = GROUND_Y - HIT_RADIUS

    if (hit_pipe or hit_ground) and g["invuln_ms"] <= 0:
        if g["shield"]:
            g["shield"] = False
            g["invuln_ms"] = 1200
            play("shield_break")
            burst(g, g["x"], g["y"], [(120, 200, 255), (255, 255, 255)], 22, 260)
            g["shake_ms"] = 200
            unlock("close_call")
            if hit_ground:
                g["vel"] = FLAP_POWER
        else:
            die(g)
    elif hit_ground:
        g["vel"] = FLAP_POWER * 0.8  # invulnerable: bounce off the ground


# ---------------- Drawing helpers ----------------
def draw_text(text, fnt, pos, color=(255, 255, 255), anchor="center", shadow=True):
    label = fnt.render(text, True, color)
    rect = label.get_rect(**{anchor: pos})
    if shadow:
        screen.blit(fnt.render(text, True, (0, 0, 0)), rect.move(2, 2))
    screen.blit(label, rect)


def wrap_text(text, fnt, max_width):
    lines, current = [], ""
    for word in text.split(" "):
        test = (current + " " + word).strip()
        if fnt.size(test)[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def button(rect, label, action, enabled=True, clip=None):
    hover = enabled and rect.collidepoint(game_position(pygame.mouse.get_pos()))
    if not enabled:
        color = (90, 90, 90)
    elif hover:
        color = (80, 170, 255)
    else:
        color = (50, 120, 220)
    pygame.draw.rect(screen, color, rect, border_radius=10)
    pygame.draw.rect(screen, (255, 255, 255), rect, 2, border_radius=10)
    draw_text(label, button_font, rect.center, shadow=False)
    if enabled and (clip is None or clip.contains(rect)):
        buttons.append((rect, action))


def click_buttons(pos):
    """Runs the closest button under the pointer, with forgiving Android touch targets."""
    hit_padding = 48 if ANDROID else 0
    candidates = [
        (rect, action)
        for rect, action in buttons
        if rect.inflate(hit_padding, hit_padding).collidepoint(pos)
    ]
    if not candidates:
        return False

    rect, action = min(
        candidates,
        key=lambda candidate: (
            (candidate[0].centerx - pos[0]) ** 2
            + (candidate[0].centery - pos[1]) ** 2
        ),
    )
    buttons.clear()
    action()
    return True


def draw_menu_background():
    screen.blit(current_bg(), (0, 0))
    screen.blit(overlay, (0, 0))


def draw_toasts():
    if not toasts:
        return
    label = small_font.render(toasts[0][0], True, (255, 255, 255))
    rect = pygame.Rect(0, 0, label.get_width() + 30, 40)
    rect.center = (WIDTH // 2, HEIGHT - 70)
    pygame.draw.rect(screen, (20, 20, 40), rect, border_radius=12)
    pygame.draw.rect(screen, (255, 215, 0), rect, 2, border_radius=12)
    screen.blit(label, label.get_rect(center=rect.center))


# ---------------- Scenes ----------------
def draw_menu():
    draw_menu_background()
    draw_text("FLAPPY GAME", title_font, (WIDTH // 2, ui_y(80)))
    draw_text(f"Coins: {save['coins']}", small_font, (WIDTH // 2, ui_y(130)), (255, 215, 0))
    draw_text(f"Best score: {save['best']}", tiny_font, (WIDTH // 2, ui_y(155)))

    items = []
    if resume_available():
        items.append(("Resume", resume_game))
    items += [
        ("Start Game", start_game),
        ("Shop", lambda: go("shop")),
        ("Achievements", lambda: go("achievements")),
        ("Settings", lambda: go("settings")),
    ]
    if not WEB:  # a Quit button makes no sense inside a web page
        items.append(("Quit", quit_game))
    y = ui_y(185)
    button_step = ui_y(245) - ui_y(185)
    for label, action in items:
        button(pygame.Rect(WIDTH // 2 - 110, y, 220, 48), label, action)
        y += button_step


def draw_settings():
    draw_menu_background()
    draw_text("SETTINGS", font, (WIDTH // 2, ui_y(60)))

    rows = [("Music volume", "music_vol", 160), ("Sound effects volume", "sfx_vol", 290)]
    for label, key, y in rows:
        draw_text(label, small_font, (WIDTH // 2, ui_y(y)))
        pct = int(round(save[key] * 100))
        button(pygame.Rect(60, ui_y(y + 30), 60, 50), "-", lambda k=key: change_volume(k, -0.1))
        draw_text(f"{pct}%", button_font, (WIDTH // 2, ui_y(y + 55)))
        button(pygame.Rect(280, ui_y(y + 30), 60, 50), "+", lambda k=key: change_volume(k, 0.1))

    draw_text("Your progress is saved automatically.", tiny_font, (WIDTH // 2, ui_y(430)))
    button(pygame.Rect(WIDTH // 2 - 90, ui_y(500), 180, 50), "Back", lambda: go("menu"))


def draw_achievements():
    draw_menu_background()
    draw_text("ACHIEVEMENTS", font, (WIDTH // 2, ui_y(42)))
    done = len(save["achievements"])
    draw_text(f"{done}/{len(ACHIEVEMENTS)} unlocked", tiny_font, (WIDTH // 2, ui_y(78)))
    y = ui_y(105)
    row_step = ui_y(171) - ui_y(105)
    for key, name, desc in ACHIEVEMENTS:
        unlocked = key in save["achievements"]
        row = pygame.Rect(20, y, 360, ui_y(58))
        pygame.draw.rect(screen, (30, 30, 50), row, border_radius=12)
        pygame.draw.rect(screen, (255, 215, 0) if unlocked else (120, 120, 120), row, 2, border_radius=12)
        pygame.draw.circle(screen, (70, 200, 100) if unlocked else (90, 90, 90), (row.x + 30, row.centery), 15)
        if unlocked:
            pygame.draw.lines(
                screen, (255, 255, 255), False,
                [(row.x + 23, row.centery), (row.x + 28, row.centery + 6), (row.x + 38, row.centery - 6)], 3,
            )
        draw_text(name, small_font, (row.x + 58, row.y + ui_y(8)), anchor="topleft")
        draw_text(desc, tiny_font, (row.x + 58, row.y + ui_y(34)), (200, 200, 200), anchor="topleft")
        y += row_step
    button(pygame.Rect(WIDTH // 2 - 90, ui_y(530), 180, 50), "Back", lambda: go("menu"))


def draw_shop():
    global shop_scroll
    draw_menu_background()
    draw_text("SHOP", font, (15, ui_y(12)), anchor="topleft")
    draw_text(f"Coins: {save['coins']}", small_font, (WIDTH - 15, ui_y(20)), (255, 215, 0), anchor="topright")
    draw_text("Collect coins in the pipes + 10 coins per minute played!", tiny_font, (WIDTH // 2, ui_y(68)))

    max_scroll = max(0, len(CHARACTERS) * ui_y(ROW_PITCH) - LIST_AREA.height)
    shop_scroll = max(0, min(shop_scroll, max_scroll))

    screen.set_clip(LIST_AREA)
    for i, char in enumerate(CHARACTERS):
        name = char["name"]
        row = pygame.Rect(LIST_AREA.x, LIST_AREA.y + i * ui_y(ROW_PITCH) - shop_scroll, LIST_AREA.width, ui_y(ROW_H))
        pygame.draw.rect(screen, (30, 30, 50), row, border_radius=12)
        pygame.draw.rect(screen, (255, 255, 255), row, 2, border_radius=12)
        screen.blit(char_previews[name], (row.x + 12, row.y + ui_y(16)))
        draw_text(name, button_font, (row.x + 70, row.y + ui_y(6)), anchor="topleft")
        draw_text(char.get("perk", ""), tiny_font, (row.x + 70, row.y + ui_y(32)), (170, 210, 255), anchor="topleft")

        owned = name in save["owned"]
        selected = save["selected"] == name
        btn = pygame.Rect(row.right - 110, row.y + ui_y(18), 98, ui_y(40))
        if owned:
            status = "Owned" if char["price"] > 0 else "Free"
            draw_text(status, tiny_font, (row.x + 70, row.y + ui_y(52)), (150, 255, 150), anchor="topleft")
            if selected:
                button(btn, "Selected", lambda: None, enabled=False, clip=LIST_AREA)
            else:
                button(btn, "Select", lambda n=name: select(n), clip=LIST_AREA)
        else:
            can_buy = save["coins"] >= char["price"]
            color = (255, 215, 0) if can_buy else (255, 120, 120)
            draw_text(f"{char['price']} coins", tiny_font, (row.x + 70, row.y + ui_y(52)), color, anchor="topleft")
            button(btn, "Buy", lambda n=name: buy(n), enabled=can_buy, clip=LIST_AREA)
    screen.set_clip(None)

    if max_scroll > 0:
        draw_text("Scroll to see more", tiny_font, (WIDTH // 2, ui_y(508)))
    button(pygame.Rect(WIDTH // 2 - 90, ui_y(530), 180, 50), "Back", lambda: go("menu"))


def draw_pipe(pipe):
    top, bottom, top_cap, bottom_cap = pipe_parts(pipe)
    for rect in (top, bottom):
        if rect.height > 0:
            pygame.draw.rect(screen, (40, 170, 70), rect)
            pygame.draw.rect(screen, (20, 100, 40), rect, 3)
    for rect in (top_cap, bottom_cap):
        pygame.draw.rect(screen, (60, 195, 90), rect)
        pygame.draw.rect(screen, (20, 100, 40), rect, 3)


def draw_item(item):
    t = pygame.time.get_ticks() / 1000.0
    bob = math.sin(t * 5 + item["x"] * 0.02) * 3
    cx, cy = int(item["x"]), int(item["y"] + bob)
    if item["type"] == "coin":
        width = max(5, int(abs(math.cos(t * 5 + item["x"] * 0.02)) * ITEM_RADIUS * 2))
        rect = pygame.Rect(0, 0, width, ITEM_RADIUS * 2)
        rect.center = (cx, cy)
        pygame.draw.ellipse(screen, (255, 215, 0), rect)
        pygame.draw.ellipse(screen, (200, 150, 0), rect, 3)
    else:
        pygame.draw.circle(screen, (120, 200, 255), (cx, cy), ITEM_RADIUS + 2)
        pygame.draw.circle(screen, (255, 255, 255), (cx, cy), ITEM_RADIUS + 2, 3)
        draw_text("S", small_font, (cx, cy), (20, 60, 120), shadow=False)


def draw_bird(g):
    img = char_imgs[save["selected"]]
    if g["phase"] == "dead":
        angle = -g["spin"]
    else:
        angle = max(-30, min(30, -g["vel"] * 0.05))
    scale = 1.0 + 0.25 * (g["flap_ms"] / 140.0)
    rotated = pygame.transform.rotozoom(img, angle, scale)
    center = (int(g["x"]), int(g["y"]))
    blink = g["invuln_ms"] > 0 and (g["invuln_ms"] // 100) % 2 == 0
    if not blink:
        screen.blit(rotated, rotated.get_rect(center=center))
    if g["shield"]:
        screen.blit(shield_surface, shield_surface.get_rect(center=center))


def draw_world(g):
    screen.blit(current_bg(), (0, 0))
    if g["score"] >= RAGE_SCORE:
        pulse = 35 + int(25 * (1 + math.sin(pygame.time.get_ticks() / 150.0)))
        rage_surface.set_alpha(pulse)
        screen.blit(rage_surface, (0, 0))

    for pipe in g["pipes"]:
        draw_pipe(pipe)
    for item in g["items"]:
        draw_item(item)

    # Ground
    pygame.draw.rect(screen, (222, 184, 108), (0, GROUND_Y, WIDTH, GROUND_H))
    pygame.draw.rect(screen, (90, 170, 60), (0, GROUND_Y, WIDTH, 8))
    offset = int(g["scroll"]) % 40
    for x in range(-40, WIDTH + 40, 40):
        pygame.draw.line(screen, (190, 150, 80), (x - offset, GROUND_Y + 10), (x - offset - 12, HEIGHT), 4)

    draw_bird(g)
    for p in g["particles"]:
        pygame.draw.circle(screen, p["color"], (int(p["x"]), int(p["y"])), p["r"])

    # Screen shake
    if g["shake_ms"] > 0:
        snapshot = screen.copy()
        strength = max(1, g["shake_ms"] // 45)
        screen.fill((0, 0, 0))
        screen.blit(snapshot, (random.randint(-strength, strength), random.randint(-strength, strength)))


def draw_death_panel(g):
    text, image_file = g["death_msg"]
    panel_rect = death_panel.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    screen.blit(death_panel, panel_rect)
    draw_text("GAME OVER", font, (WIDTH // 2, panel_rect.y + 30), (255, 90, 90))

    # Your custom picture, above the message
    img = death_images.get(image_file)
    if img:
        screen.blit(img, img.get_rect(center=(WIDTH // 2, panel_rect.y + 115)))

    lines = wrap_text(text, msg_font, 300)
    line_h = 26
    center_y = panel_rect.y + (237 if img else 190)
    first_y = center_y - (len(lines) - 1) * line_h / 2
    for i, line in enumerate(lines):
        draw_text(line, msg_font, (WIDTH // 2, int(first_y + i * line_h)), (255, 235, 130))

    draw_text(f"Score: {g['score']}   Best: {save['best']}", small_font, (WIDTH // 2, panel_rect.y + 318))
    if g["run_coins"]:
        draw_text(f"+{g['run_coins']} coins this run", tiny_font, (WIDTH // 2, panel_rect.y + 342), (255, 215, 0))

    if g["dead_ms"] >= 300:
        button(pygame.Rect(panel_rect.x + 20, panel_rect.y + 368, 140, 44), "Share", share_score)
        button(pygame.Rect(panel_rect.right - 160, panel_rect.y + 368, 140, 44), "Menu", pause_to_menu)
    draw_text("Tap anywhere or press SPACE to retry", tiny_font, (WIDTH // 2, panel_rect.y + 432))


def draw_game():
    g = game
    draw_world(g)

    draw_text(str(g["score"]), font, (WIDTH // 2, 40))
    draw_text(f"Coins: {save['coins']}", tiny_font, (10, 10), (255, 215, 0), anchor="topleft")
    pygame.draw.rect(screen, (40, 40, 40), (10, 32, 100, 8))
    fill = int(100 * save["play_ms"] / MS_PER_REWARD)
    pygame.draw.rect(screen, (255, 215, 0), (10, 32, fill, 8))
    if ANDROID:
        button(pygame.Rect(WIDTH - 94, 8, 84, 44), "Menu", pause_to_menu)
    else:
        draw_text("ESC = menu", tiny_font, (WIDTH - 10, 10), anchor="topright")
    if g["shield"]:
        shield_y = 60 if ANDROID else 30
        draw_text("SHIELD", tiny_font, (WIDTH - 10, shield_y), (150, 220, 255), anchor="topright")

    if g["banner_ms"] > 0:
        bump = 1 + int(4 * math.sin(g["banner_ms"] / 80.0))
        draw_text(g["banner"], title_font, (WIDTH // 2, 130 + bump), (255, 120, 80))

    if g["phase"] == "ready":
        draw_text("Tap or press SPACE", small_font, (WIDTH // 2, HEIGHT // 2 - 80))
        draw_text("to start", small_font, (WIDTH // 2, HEIGHT // 2 - 50))
        char = char_by_name[save["selected"]]
        draw_text(f"{char['name']}: {char.get('perk', '')}", tiny_font, (WIDTH // 2, HEIGHT // 2 + 70), (200, 225, 255))
    elif g["phase"] == "playing" and g["countdown"] > 0:
        draw_text(str(int(g["countdown"] // 1000) + 1), title_font, (WIDTH // 2, HEIGHT // 2 - 60))
        draw_text("Get ready...", small_font, (WIDTH // 2, HEIGHT // 2 - 10))
    elif g["phase"] == "dead":
        draw_death_panel(g)


# ---------------- Main loop ----------------
async def main():
    global shop_scroll

    while True:
        dt_ms = min(clock.tick(FPS), 33)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            elif event.type == APP_BACKGROUND_EVENT:
                # the player switched apps / locked the phone: pause and save
                if scene == "game":
                    pause_to_menu()
                else:
                    write_save()
            elif event.type == pygame.KEYDOWN and event.key in BACK_KEYS:
                if scene == "game":
                    pause_to_menu()
                elif scene in ("settings", "shop", "achievements"):
                    go("menu")
            elif event.type == pygame.MOUSEWHEEL and scene == "shop":
                shop_scroll -= event.y * 40
            elif scene == "game":
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_UP):
                    flap()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    position = game_position(event.pos)
                    if not click_buttons(position):
                        flap()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                click_buttons(game_position(event.pos))

        update_toasts(dt_ms)
        if scene == "game" and game:
            update_game(dt_ms)

        buttons.clear()
        if scene == "menu":
            draw_menu()
        elif scene == "settings":
            draw_settings()
        elif scene == "shop":
            draw_shop()
        elif scene == "achievements":
            draw_achievements()
        elif scene == "game":
            draw_game()
        draw_toasts()

        if ANDROID:
            pygame.transform.scale(screen, display.get_size(), display)
        pygame.display.flip()
        await asyncio.sleep(0)  # REQUIRED for the web: lets the browser breathe


asyncio.run(main())
