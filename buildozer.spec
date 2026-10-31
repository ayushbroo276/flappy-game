[app]

title = Modi Flappy
package.name = flappygame
package.domain = org.flappybird
source.dir = .
source.include_exts = py,jpg,jpeg,png,wav,ogg,mp3,json,ttf
source.exclude_dirs = .git,.buildozer,bin,__pycache__,build,dist,tests
version = 1.0.0
requirements = python3,pygame,pyjnius

orientation = portrait
fullscreen = 1

android.permissions = INTERNET,VIBRATE
android.api = 34
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True

p4a.bootstrap = sdl2
p4a.branch = v2023.09.16

[buildozer]
log_level = 2
warn_on_root = 1
