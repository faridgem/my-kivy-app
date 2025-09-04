[app]
title = MyKivyApp
package.name = mykivyapp
package.domain = com.YOURDOMAIN # e.g. com.fabi
source.dir = .
source.include_exts = py,kv,png,jpg,ttf,atlas,json,txt,ini,md
requirements = python3,kivy # add others: requests, urllib3, etc.
orientation = portrait
fullscreen = 0


# You can pin/adjust these if needed
# android.api = 33 # Target API (optional; Buildozer picks sane default)
# android.minapi = 21 # Minimum supported
android.archs = arm64-v8a, armeabi-v7a


# Permissions (add only if needed)
# android.permissions = INTERNET,ACCESS_NETWORK_STATE


# App icons/splash (optional, provide files)
# icon.filename = assets/icon.png
# presplash.filename = assets/presplash.png


[buildozer]
log_level = 2
warn_on_root = 0