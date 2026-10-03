[app]

title = Flappy Game
package.name = flappygame
package.domain = org.flappybird
source.dir = .
source.include_exts = py,jpg,jpeg,png,wav,ogg,mp3,json
source.exclude_dirs = .git,.buildozer,bin,__pycache__
version = 1.0.0
requirements = python3,pygame
orientation = portrait
fullscreen = 1

android.api = 35
android.minapi = 23
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True

p4a.bootstrap = sdl2

