"""macOS window utilities — find & capture Slay the Spire window.

Uses CoreGraphics via ctypes (no external deps).
"""

import base64
import ctypes
import ctypes.util
import logging
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

logger = logging.getLogger(__name__)

# ─── CoreGraphics ctypes bindings ───────────────────────────────────────────

_cg_lib_path = ctypes.util.find_library("CoreGraphics")
if _cg_lib_path is None:
    _msg = "CoreGraphics framework not found"
    raise RuntimeError(_msg)
_cg: Any = ctypes.cdll.LoadLibrary(_cg_lib_path)

_CFSTRING_ENCODING_UTF8 = 0x08000100
_CFNUMBER_TYPE_SINT64 = 4

_CFSTRING_CREATE = _cg.CFStringCreateWithCString
_CFSTRING_CREATE.restype = ctypes.c_void_p
_CFSTRING_CREATE.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]

_CFSTRING_GET_CSTRING_PTR = _cg.CFStringGetCStringPtr
_CFSTRING_GET_CSTRING_PTR.restype = ctypes.c_char_p
_CFSTRING_GET_CSTRING_PTR.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

_CFNUMBER_GET_VALUE = _cg.CFNumberGetValue
_CFNUMBER_GET_VALUE.restype = ctypes.c_int
_CFNUMBER_GET_VALUE.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]

_CFARRAY_GET_COUNT = _cg.CFArrayGetCount
_CFARRAY_GET_COUNT.restype = ctypes.c_int64
_CFARRAY_GET_COUNT.argtypes = [ctypes.c_void_p]

_CFARRAY_GET_VALUE = _cg.CFArrayGetValueAtIndex
_CFARRAY_GET_VALUE.restype = ctypes.c_void_p
_CFARRAY_GET_VALUE.argtypes = [ctypes.c_void_p, ctypes.c_int64]

_CFDICT_GET_VALUE = _cg.CFDictionaryGetValue
_CFDICT_GET_VALUE.restype = ctypes.c_void_p
_CFDICT_GET_VALUE.argtypes = [ctypes.c_void_p, ctypes.c_void_p]


def _cfstr(s: str) -> ctypes.c_void_p:
    return _CFSTRING_CREATE(None, s.encode(), _CFSTRING_ENCODING_UTF8)


def _cfstr_val(p: ctypes.c_void_p) -> str:
    if not p:
        return ""
    v = _CFSTRING_GET_CSTRING_PTR(p, _CFSTRING_ENCODING_UTF8)
    return v.decode() if v else ""


def _cfnum_val(p: ctypes.c_void_p) -> int | None:
    if not p:
        return None
    v = ctypes.c_int64()
    _CFNUMBER_GET_VALUE(p, _CFNUMBER_TYPE_SINT64, ctypes.byref(v))
    return v.value


# Pre-created key CFStrings
_CG_WINDOW_OWNER_NAME = _cfstr("kCGWindowOwnerName")
_CG_WINDOW_NAME = _cfstr("kCGWindowName")
_CG_WINDOW_NUMBER = _cfstr("kCGWindowNumber")
_CG_WINDOW_LAYER = _cfstr("kCGWindowLayer")

# ─── Public API ─────────────────────────────────────────────────────────────


def list_windows() -> list[dict[str, Any]]:
    """Return list of all on-screen windows with id, owner, title, layer."""
    cg_copy = _cg.CGWindowListCopyWindowInfo
    cg_copy.restype = ctypes.c_void_p
    cg_copy.argtypes = [ctypes.c_uint32, ctypes.c_uint32]

    arr = cg_copy(0, 0)
    count = _CFARRAY_GET_COUNT(arr)

    windows: list[dict[str, Any]] = []
    for i in range(count):
        d = _CFARRAY_GET_VALUE(arr, i)
        owner = _cfstr_val(_CFDICT_GET_VALUE(d, _CG_WINDOW_OWNER_NAME))
        title = _cfstr_val(_CFDICT_GET_VALUE(d, _CG_WINDOW_NAME))
        wid = _cfnum_val(_CFDICT_GET_VALUE(d, _CG_WINDOW_NUMBER))
        layer = _cfnum_val(_CFDICT_GET_VALUE(d, _CG_WINDOW_LAYER))
        windows.append(
            {
                "id": wid,
                "owner": owner,
                "title": title,
                "layer": layer,
            }
        )
    return windows


def find_window(title_contains: str = "Modded Slay the Spire") -> dict[str, Any] | None:
    """Find the first normal-layer window whose title contains *title_contains*."""
    fallback: dict[str, Any] | None = None
    for w in list_windows():
        title = w.get("title")
        layer = w.get("layer")
        if title and title_contains in title:
            if layer == 0:
                return w
            if fallback is None:
                fallback = w
    return fallback


def capture(window_id: int) -> str:
    """Capture a window by id, return base64-encoded PNG."""
    with NamedTemporaryFile(suffix=".png") as tmp:
        subprocess.run(
            ["screencapture", "-l", str(window_id), tmp.name],
            check=True,
            capture_output=True,
            timeout=10,
        )
        return base64.b64encode(Path(tmp.name).read_bytes()).decode()
