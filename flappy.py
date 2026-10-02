"""
Flappy game with menu, resume, settings, coins and a character shop (pygame)
Each character has its OWN song and its OWN background.

Put these files in the SAME folder as this script (names are set in CHARACTERS):
    bird.jpg, bird_red.jpg, bird_blue.jpg, bird_green.jpg, bird_purple.jpg
    background.jpg, background_red.jpg, background_blue.jpg, ...
    music.mp3, music_red.mp3, music_blue.mp3, ...
    death.wav   (shared death sound)

If a character's song or background is missing, the free "Classic" one is
used instead. If a character image is missing, a colored bird is drawn.

Controls: SPACE or click = flap.  ESC = pause / go back to the menu.
Coins: you earn 10 coins for every 1 minute you actually play.
Progress (coins, owned characters, settings) is saved in save.json.
"""
import json
import os
import random
import sys

import pygame

# ---------- Settings you can change ----------
DEATH_SOUND_FILE = "death.wav"
SAVE_FILE = "save.json"

# Characters in the shop. The first one is free and owned from the start,
# and its song/background are used whenever another character's are missing.
# Each character: name, image, price in coins, placeholder color,
#                 its own song and its own background.
CHARACTERS = [
    {"name": "Classic", "file": "bird.jpg", "price": 0, "color": (255, 220, 0),
     "music": "music.mp3", "background": "background.jpg"},
    {"name": "Red", "file": "bird_red.jpg", "price": 30, "color": (230, 70, 70),
     "music": "music_red.mp3", "background": "background_red.jpg"},
    {"name": "Blue", "file": "bird_blue.jpg", "price": 50, "color": (70, 130, 240),
     "music": "music_blue.mp3", "background": "background_blue.jpg"},
    {"name": "Green", "file": "bird_green.jpg", "price": 0, "color": (60, 190, 90),
     "music": "music_green.mp3", "background": "background_green.jpg"},
    {"name": "Purple", "file": "bird_purple.jpg", "price": 120, "color": (160, 90, 220),
     "music": "music_purple.mp3", "background": "background_purple.jpg"},
]

COINS_PER_REWARD = 10        # coins you get...
MS_PER_REWARD = 60000        # ...for every 60,000 ms (1 minute) of play
RESUME_COUNTDOWN_MS = 3000   # 3 second countdown after pressing Resume

WIDTH, HEIGHT = 400, 600
FPS = 60
GRAVITY = 0.45
FLAP_POWER = -8
PIPE_GAP = 170
PIPE_SPEED = 3
PIPE_WIDTH = 70
PIPE_SPAWN_MS = 1500
BIRD_SIZE = (50, 50)
# ---------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def file_path(name):
    return os.path.join(BASE_DIR, name)


pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Flappy Game")
clock = pygame.time.Clock()
title_font = pygame.font.SysFont(None, 64)
font = pygame.font.SysFont(None, 48)
button_font = pygame.font.SysFont(None, 34)
small_font = pygame.font.SysFont(None, 28)
tiny_font = pygame.font.SysFont(None, 22)

# ---------------- Save data ----------------
DEFAULT_SAVE = {
    "coins": 0,
    "owned": [CHARACTERS[0]["name"]],
    "selected": CHARACTERS[0]["name"],
    "music_vol": 0.5,
    "sfx_vol": 1.0,
    "play_ms": 0,
    "best": 0,
}
char_by_name = {c["name"]: c for c in CHARACTERS}


def load_save():
    data = dict(DEFAULT_SAVE)
    try:
        with open(file_path(SAVE_FILE), "r", encoding="utf-8") as f:
            data.update(json.load(f))
    except (OSError, ValueError):
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
    return data


def write_save():
    try:
        with open(file_path(SAVE_FILE), "w", encoding="utf-8") as f:
            json.dump(save, f)
    except OSError:
        print("Could not write save file.")


save = load_save()

# ---------------- Images ----------------


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
        return pygame.transform.smoothscale(img, size)
    except (pygame.error, FileNotFoundError):
        return make_placeholder(size, char["color"])


def load_background(file_name):
    """Returns a background Surface, or None if the file can't be loaded."""
    try:
        img = pygame.image.load(file_path(file_name)).convert()
        return pygame.transform.smoothscale(img, (WIDTH, HEIGHT))
    except (pygame.error, FileNotFoundError):
        return None


for c in CHARACTERS:
    for key in ("file", "music", "background"):
        if not os.path.exists(file_path(c[key])):
            print(f"{c[key]} not found ({c['name']} {key}); using a fallback.")

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

# ---------------- Sounds ----------------
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


apply_volumes()


def music_path_for(name):
    """The selected character's song, or Classic's song if it is missing."""
    own = file_path(char_by_name[name]["music"])
    if os.path.exists(own):
        return own
    fallback = file_path(CHARACTERS[0]["music"])
    return fallback if os.path.exists(fallback) else None


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
        print(f"Could not play {path}. Try converting it to .ogg or .wav.")


def stop_music():
    pygame.mixer.music.stop()


# ---------------- Game state ----------------
scene = "menu"        # "menu", "settings", "shop", "game"
game = None           # None = no game yet
toast_ms = 0          # "+10 coins" message timer
shop_scroll = 0
buttons = []          # filled every frame by button()

LIST_AREA = pygame.Rect(10, 85, 380, 415)
ROW_H = 76
ROW_PITCH = 82


def new_game():
    return {
        "bird": pygame.Rect(80, HEIGHT // 2 - BIRD_SIZE[1] // 2, BIRD_SIZE[0], BIRD_SIZE[1]),
        "vel": 0.0,
        "pipes": [],
        "score": 0,
        "spawn_timer": 0,
        "phase": "ready",   # "ready" -> "playing" -> "dead"
        "countdown": 0,
        "dead_ms": 0,
    }


def spawn_pipe():
    return {"x": WIDTH, "gap_y": random.randint(150, HEIGHT - 150), "passed": False}


def pipe_rects(pipe):
    top = pygame.Rect(pipe["x"], 0, PIPE_WIDTH, pipe["gap_y"] - PIPE_GAP // 2)
    bottom = pygame.Rect(
        pipe["x"], pipe["gap_y"] + PIPE_GAP // 2,
        PIPE_WIDTH, HEIGHT - (pipe["gap_y"] + PIPE_GAP // 2),
    )
    return top, bottom


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


def select(name):
    if name in save["owned"]:
        save["selected"] = name
        write_save()


def change_volume(key, delta):
    save[key] = round(min(1.0, max(0.0, save[key] + delta)), 1)
    apply_volumes()
    write_save()
    if key == "sfx_vol" and death_sound:
        death_sound.play()  # preview


def flap():
    global game
    phase = game["phase"]
    if phase == "ready":
        game["phase"] = "playing"
        game["vel"] = FLAP_POWER
        start_music()
    elif phase == "playing":
        if game["countdown"] <= 0:
            game["vel"] = FLAP_POWER
    elif phase == "dead" and game["dead_ms"] >= 500:
        game = new_game()
        game["phase"] = "playing"
        game["vel"] = FLAP_POWER
        start_music()


def update_game(dt):
    global toast_ms
    g = game
    if g["phase"] == "dead":
        g["dead_ms"] += dt
        return
    if g["phase"] != "playing":
        return
    if g["countdown"] > 0:
        g["countdown"] -= dt
        return

    # Coins: only count time while really playing
    save["play_ms"] += dt
    if save["play_ms"] >= MS_PER_REWARD:
        rewards = int(save["play_ms"] // MS_PER_REWARD)
        save["play_ms"] -= rewards * MS_PER_REWARD
        save["coins"] += rewards * COINS_PER_REWARD
        toast_ms = 2000
        write_save()

    # Bird physics
    g["vel"] += GRAVITY
    g["bird"].y += int(g["vel"])

    # Pipes
    g["spawn_timer"] += dt
    if g["spawn_timer"] >= PIPE_SPAWN_MS:
        g["pipes"].append(spawn_pipe())
        g["spawn_timer"] = 0
    for pipe in g["pipes"]:
        pipe["x"] -= PIPE_SPEED
        if not pipe["passed"] and pipe["x"] + PIPE_WIDTH < g["bird"].x:
            pipe["passed"] = True
            g["score"] += 1
    g["pipes"] = [p for p in g["pipes"] if p["x"] > -PIPE_WIDTH]

    # Collisions (slightly forgiving hitbox)
    hitbox = g["bird"].inflate(-12, -12)
    died = hitbox.top <= 0 or hitbox.bottom >= HEIGHT
    for pipe in g["pipes"]:
        top, bottom = pipe_rects(pipe)
        if hitbox.colliderect(top) or hitbox.colliderect(bottom):
            died = True

    if died:
        g["phase"] = "dead"
        g["dead_ms"] = 0
        save["best"] = max(save["best"], g["score"])
        stop_music()
        if death_sound:
            death_sound.play()
        write_save()


# ---------------- Drawing helpers ----------------
def draw_text(text, fnt, pos, color=(255, 255, 255), anchor="center", shadow=True):
    label = fnt.render(text, True, color)
    rect = label.get_rect(**{anchor: pos})
    if shadow:
        screen.blit(fnt.render(text, True, (0, 0, 0)), rect.move(2, 2))
    screen.blit(label, rect)


def button(rect, label, action, enabled=True, clip=None):
    hover = enabled and rect.collidepoint(pygame.mouse.get_pos())
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


def draw_menu_background():
    screen.blit(current_bg(), (0, 0))
    screen.blit(overlay, (0, 0))


# ---------------- Scenes ----------------
def draw_menu():
    draw_menu_background()
    draw_text("FLAPPY GAME", title_font, (WIDTH // 2, 80))
    draw_text(f"Coins: {save['coins']}", small_font, (WIDTH // 2, 135), (255, 215, 0))
    draw_text(f"Best score: {save['best']}", tiny_font, (WIDTH // 2, 160))

    items = []
    if resume_available():
        items.append(("Resume", resume_game))
    items += [
        ("Start Game", start_game),
        ("Shop", lambda: go("shop")),
        ("Settings", lambda: go("settings")),
        ("Quit", quit_game),
    ]
    y = 195
    for label, action in items:
        button(pygame.Rect(WIDTH // 2 - 110, y, 220, 52), label, action)
        y += 66


def draw_settings():
    draw_menu_background()
    draw_text("SETTINGS", font, (WIDTH // 2, 60))

    rows = [("Music volume", "music_vol", 160), ("Sound effects volume", "sfx_vol", 290)]
    for label, key, y in rows:
        draw_text(label, small_font, (WIDTH // 2, y))
        pct = int(round(save[key] * 100))
        button(pygame.Rect(60, y + 30, 60, 50), "-", lambda k=key: change_volume(k, -0.1))
        draw_text(f"{pct}%", button_font, (WIDTH // 2, y + 55))
        button(pygame.Rect(280, y + 30, 60, 50), "+", lambda k=key: change_volume(k, 0.1))

    draw_text("Your progress is saved automatically.", tiny_font, (WIDTH // 2, 430))
    button(pygame.Rect(WIDTH // 2 - 90, 500, 180, 50), "Back", lambda: go("menu"))


def draw_shop():
    global shop_scroll
    draw_menu_background()
    draw_text("SHOP", font, (15, 12), anchor="topleft")
    draw_text(f"Coins: {save['coins']}", small_font, (WIDTH - 15, 20), (255, 215, 0), anchor="topright")
    draw_text("Earn 10 coins for every minute you play!", tiny_font, (WIDTH // 2, 68))

    max_scroll = max(0, len(CHARACTERS) * ROW_PITCH - LIST_AREA.height)
    shop_scroll = max(0, min(shop_scroll, max_scroll))

    screen.set_clip(LIST_AREA)
    for i, char in enumerate(CHARACTERS):
        name = char["name"]
        row = pygame.Rect(LIST_AREA.x, LIST_AREA.y + i * ROW_PITCH - shop_scroll, LIST_AREA.width, ROW_H)
        pygame.draw.rect(screen, (30, 30, 50), row, border_radius=12)
        pygame.draw.rect(screen, (255, 255, 255), row, 2, border_radius=12)
        screen.blit(char_previews[name], (row.x + 12, row.y + 16))
        draw_text(name, button_font, (row.x + 70, row.y + 12), anchor="topleft")

        owned = name in save["owned"]
        selected = save["selected"] == name
        btn = pygame.Rect(row.right - 110, row.y + 18, 98, 40)
        if owned:
            status = "Owned" if char["price"] > 0 else "Free"
            draw_text(status, tiny_font, (row.x + 70, row.y + 46), (150, 255, 150), anchor="topleft")
            if selected:
                button(btn, "Selected", lambda: None, enabled=False, clip=LIST_AREA)
            else:
                button(btn, "Select", lambda n=name: select(n), clip=LIST_AREA)
        else:
            can_buy = save["coins"] >= char["price"]
            color = (255, 215, 0) if can_buy else (255, 120, 120)
            draw_text(f"{char['price']} coins", tiny_font, (row.x + 70, row.y + 46), color, anchor="topleft")
            button(btn, "Buy", lambda n=name: buy(n), enabled=can_buy, clip=LIST_AREA)
    screen.set_clip(None)

    if max_scroll > 0:
        draw_text("Scroll to see more", tiny_font, (WIDTH // 2, 508))
    button(pygame.Rect(WIDTH // 2 - 90, 530, 180, 50), "Back", lambda: go("menu"))


def draw_game():
    g = game
    screen.blit(current_bg(), (0, 0))
    for pipe in g["pipes"]:
        for rect in pipe_rects(pipe):
            pygame.draw.rect(screen, (40, 170, 70), rect)
            pygame.draw.rect(screen, (20, 100, 40), rect, 3)

    angle = max(-30, min(30, -g["vel"] * 3))
    rotated = pygame.transform.rotate(char_imgs[save["selected"]], angle)
    screen.blit(rotated, rotated.get_rect(center=g["bird"].center))

    draw_text(str(g["score"]), font, (WIDTH // 2, 40))

    # Coin HUD + progress to the next reward
    draw_text(f"Coins: {save['coins']}", tiny_font, (10, 10), (255, 215, 0), anchor="topleft")
    pygame.draw.rect(screen, (40, 40, 40), (10, 32, 100, 8))
    fill = int(100 * save["play_ms"] / MS_PER_REWARD)
    pygame.draw.rect(screen, (255, 215, 0), (10, 32, fill, 8))
    draw_text("ESC = menu", tiny_font, (WIDTH - 10, 10), anchor="topright")

    if toast_ms > 0:
        draw_text(f"+{COINS_PER_REWARD} coins!", font, (WIDTH // 2, 110), (255, 215, 0))

    if g["phase"] == "ready":
        draw_text("Press SPACE or click", small_font, (WIDTH // 2, HEIGHT // 2 - 80))
        draw_text("to start", small_font, (WIDTH // 2, HEIGHT // 2 - 50))
    elif g["phase"] == "playing" and g["countdown"] > 0:
        draw_text(str(int(g["countdown"] // 1000) + 1), title_font, (WIDTH // 2, HEIGHT // 2 - 60))
        draw_text("Get ready...", small_font, (WIDTH // 2, HEIGHT // 2 - 10))
    elif g["phase"] == "dead":
        draw_text("GAME OVER", font, (WIDTH // 2, HEIGHT // 2 - 70), (255, 80, 80))
        draw_text(f"Score: {g['score']}   Best: {save['best']}", small_font, (WIDTH // 2, HEIGHT // 2 - 20))
        draw_text("SPACE or click to retry", small_font, (WIDTH // 2, HEIGHT // 2 + 20))
        draw_text("ESC for menu", tiny_font, (WIDTH // 2, HEIGHT // 2 + 55))


# ---------------- Main loop ----------------
while True:
    dt = min(clock.tick(FPS), 50)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            quit_game()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if scene == "game":
                pause_to_menu()
            elif scene in ("settings", "shop"):
                go("menu")
        elif event.type == pygame.MOUSEWHEEL and scene == "shop":
            shop_scroll -= event.y * 40
        elif scene == "game":
            if (event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE) or (
                event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
            ):
                flap()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, action in buttons:
                if rect.collidepoint(event.pos):
                    action()
                    break
            buttons.clear()

    if toast_ms > 0:
        toast_ms -= dt
    if scene == "game" and game:
        update_game(dt)

    buttons.clear()
    if scene == "menu":
        draw_menu()
    elif scene == "settings":
        draw_settings()
    elif scene == "shop":
        draw_shop()
    elif scene == "game":
        draw_game()

    pygame.display.flip()