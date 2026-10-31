"""Resolve game assets from the repository's organized asset folders."""

import os
import sys


_ASSET_FOLDERS = {
    ".jpg": "images",
    ".jpeg": "images",
    ".png": "images",
    ".ttf": "fonts",
    ".mp3": "audio",
    ".ogg": "audio",
    ".wav": "audio",
}


def project_root():
    source_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if os.path.isdir(os.path.join(source_root, "assets")):
        return source_root
    return sys.prefix


def asset_path(name, base_dir):
    extension = os.path.splitext(name)[1].lower()
    try:
        folder = _ASSET_FOLDERS[extension]
    except KeyError as exc:
        raise ValueError(f"Unsupported asset file type: {extension}") from exc
    return os.path.join(base_dir, "assets", folder, name)
