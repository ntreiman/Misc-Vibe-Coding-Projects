"""Optionally read tools straight out of Fusion's own CAM tool libraries so a
tool added there counts as "owned" without also editing shop_tools.json.

Only local (user) libraries are scanned; Fusion's sample libraries list tools
nobody necessarily owns.  Any error is swallowed and reported as a message so
a quirk of the CAM API never blocks snapping.
"""

from typing import List, Tuple

import adsk.cam
import adsk.core

from ..core.snap import Tool

# Fusion tool_type values -> ToolSnap tool type.  Counterbores are plunged, so
# only centre-cutting flat endmills qualify.
TYPE_MAP = {
    "drill": "drill",
    "flat end mill": "endmill",
}


def read_local_libraries() -> Tuple[List[Tool], List[str]]:
    tools: List[Tool] = []
    notes: List[str] = []
    cam_mgr = adsk.cam.CAMManager.get()
    libs = cam_mgr.libraryManager.toolLibraries
    root = libs.urlByLocation(adsk.cam.LibraryLocations.LocalLibraryLocation)
    for url in _walk(libs, root):
        try:
            lib = libs.toolLibraryAtURL(url)
        except Exception as exc:  # noqa: BLE001
            notes.append(f"could not open {url.toString()}: {exc}")
            continue
        for tool in lib:
            try:
                ttype = _param(tool, "tool_type")
                kind = TYPE_MAP.get(str(ttype).lower())
                if not kind:
                    continue
                dia_cm = float(_param(tool, "tool_diameter"))
                desc = str(_param(tool, "tool_description") or "").strip()
                name = desc or f"{dia_cm * 10:g} mm"
                tools.append(Tool(name=name, type=kind, diameter_mm=round(dia_cm * 10, 4),
                                  available=True, category="Fusion library"))
            except Exception as exc:  # noqa: BLE001
                notes.append(f"skipped a tool in {url.toString()}: {exc}")
    return tools, notes


def _walk(libs, url):
    yield from libs.childAssetURLs(url)
    for folder in libs.childFolderURLs(url):
        yield from _walk(libs, folder)


def _param(tool, name):
    p = tool.parameters.itemByName(name)
    return p.value.value if p else None
