"""settings.json next to the add-in: output folder and post file."""

import json
import os

ADDIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(ADDIN_DIR, "settings.json")
POST_FILENAME = "Duet2Ethernet_RRF2051.cps"

DEFAULTS = {
    "output_folder": "",     # "" = ~/Downloads
    "post_path": "",         # "" = <Fusion personal posts folder>/Duet2Ethernet_RRF2051.cps
    "open_folder_when_done": False,
}


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data.update(json.load(f))
    except (OSError, ValueError):
        pass
    return data


def save(data: dict) -> None:
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def resolve_output_folder(data: dict) -> str:
    folder = data.get("output_folder") or os.path.join(os.path.expanduser("~"), "Downloads")
    return os.path.expanduser(folder)


def resolve_post_path(data: dict, personal_post_folder: str) -> str:
    path = data.get("post_path")
    if not path:
        path = os.path.join(personal_post_folder, POST_FILENAME)
    return os.path.expanduser(path)
