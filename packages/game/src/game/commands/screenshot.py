"""Capture Slay the Spire window and save as JPEG.

Uses CoreGraphics via ctypes (cross-space safe — works even when StS
is on a different macOS Space). Pillow for resize + JPEG encode.

Output::

    {"path": "/Users/harry/.sts/screenshots/20260508_025632_123_0900.jpg"}

Max 10 files retained in ~/.sts/screenshots/.
"""

import ctypes
import ctypes.util
import io
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CoreFoundation / CoreGraphics ctypes bindings
# ---------------------------------------------------------------------------

_cg_lib_path = ctypes.util.find_library("CoreGraphics")
if _cg_lib_path is None:
    msg = "CoreGraphics framework not found"
    raise RuntimeError(msg)
_cg = ctypes.cdll.LoadLibrary(_cg_lib_path)

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


class _CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class _CGSize(ctypes.Structure):
    _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]


class _CGRect(ctypes.Structure):
    _fields_ = [("origin", _CGPoint), ("size", _CGSize)]


_CGRectNull = _CGRect(_CGPoint(float("inf"), float("inf")), _CGSize(0, 0))


_CGWindowListCreateImage = _cg.CGWindowListCreateImage
_CGWindowListCreateImage.restype = ctypes.c_void_p
_CGWindowListCreateImage.argtypes = [
    _CGRect,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_uint32,
]

_CFRelease = _cg.CFRelease
_CFRelease.restype = None
_CFRelease.argtypes = [ctypes.c_void_p]

_CFDataCreateMutable = _cg.CFDataCreateMutable
_CFDataCreateMutable.restype = ctypes.c_void_p
_CFDataCreateMutable.argtypes = [ctypes.c_void_p, ctypes.c_int64]

_CFDataGetLength = _cg.CFDataGetLength
_CFDataGetLength.restype = ctypes.c_int64
_CFDataGetLength.argtypes = [ctypes.c_void_p]

_CFDataGetBytePtr = _cg.CFDataGetBytePtr
_CFDataGetBytePtr.restype = ctypes.POINTER(ctypes.c_uint8)
_CFDataGetBytePtr.argtypes = [ctypes.c_void_p]

_imageio_path = ctypes.util.find_library("ImageIO")
if _imageio_path is None:
    msg = "ImageIO framework not found"
    raise RuntimeError(msg)
_imageio: Any = ctypes.cdll.LoadLibrary(_imageio_path)

_CGImageDestinationCreateWithData = _imageio.CGImageDestinationCreateWithData
_CGImageDestinationCreateWithData.restype = ctypes.c_void_p
_CGImageDestinationCreateWithData.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.c_void_p,
]

_CGImageDestinationAddImage = _imageio.CGImageDestinationAddImage
_CGImageDestinationAddImage.restype = None
_CGImageDestinationAddImage.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
]

_CGImageDestinationFinalize = _imageio.CGImageDestinationFinalize
_CGImageDestinationFinalize.restype = ctypes.c_bool
_CGImageDestinationFinalize.argtypes = [ctypes.c_void_p]

_PNG_UTI = "public.png"
_K_CG_INCLUDE_WINDOW = 8
_K_CG_IGNORE_FRAMING = 1

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfstr(s: str) -> ctypes.c_void_p:
    return _CFSTRING_CREATE(None, s.encode(), _CFSTRING_ENCODING_UTF8)


def _cfstr_val(p: ctypes.c_void_p | None) -> str:
    if p is None:
        return ""
    v = _CFSTRING_GET_CSTRING_PTR(p, _CFSTRING_ENCODING_UTF8)
    return v.decode() if v else ""


def _cfnum_val(p: ctypes.c_void_p | None) -> int | None:
    if p is None:
        return None
    v = ctypes.c_int64()
    _CFNUMBER_GET_VALUE(p, _CFNUMBER_TYPE_SINT64, ctypes.byref(v))
    return v.value


_CG_WINDOW_OWNER_NAME = _cfstr("kCGWindowOwnerName")
_CG_WINDOW_NAME = _cfstr("kCGWindowName")
_CG_WINDOW_NUMBER = _cfstr("kCGWindowNumber")
_CG_WINDOW_LAYER = _cfstr("kCGWindowLayer")


# ---------------------------------------------------------------------------
# Window discovery
# ---------------------------------------------------------------------------


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
        windows.append({"id": wid, "owner": owner, "title": title, "layer": layer})
    return windows


WINDOW_TITLE = "Modded Slay the Spire"


def _find_window(
    title_contains: str = WINDOW_TITLE,
) -> dict[str, Any] | None:
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


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


def _capture_raw(window_id: int) -> bytes:
    """Capture a window by id, return raw PNG bytes (cross-space safe)."""
    cg_img = _CGWindowListCreateImage(
        _CGRectNull,
        _K_CG_INCLUDE_WINDOW,
        window_id,
        _K_CG_IGNORE_FRAMING,
    )
    if not cg_img:
        msg = f"CGWindowListCreateImage returned NULL for window {window_id}"
        raise RuntimeError(msg)

    data: Any = None
    dest: Any = None
    try:
        data = _CFDataCreateMutable(None, 0)
        if not data:
            msg = "CFDataCreateMutable failed"
            raise RuntimeError(msg)

        uti = _cfstr(_PNG_UTI)
        dest = _CGImageDestinationCreateWithData(data, uti, 1, None)
        if not dest:
            msg = "CGImageDestinationCreateWithData failed"
            raise RuntimeError(msg)

        _CGImageDestinationAddImage(dest, cg_img, None)

        if not _CGImageDestinationFinalize(dest):
            msg = "CGImageDestinationFinalize failed"
            raise RuntimeError(msg)

        length = _CFDataGetLength(data)
        ptr = _CFDataGetBytePtr(data)
        return ctypes.string_at(ptr, length)
    finally:
        if dest:
            _CFRelease(dest)
        if data:
            _CFRelease(data)
        _CFRelease(cg_img)


OUTPUT_DIR = Path.home() / ".sts" / "screenshots"
MAX_FILES = 10
MAX_CAPTURE_ATTEMPTS = 5
_MAX_SCREENSHOT_DIMENSION = 1366
_SCREENSHOT_JPEG_QUALITY = 95


def _rotate_files() -> None:
    """Remove oldest files beyond MAX_FILES."""
    files = sorted(OUTPUT_DIR.glob("*.jpg"))
    while len(files) > MAX_FILES:
        logger.info(
            "removing old screenshot",
            extra={"event": "rotate_screenshot", "path": str(files[0])},
        )
        files[0].unlink()
        files = files[1:]


class ScreenshotResult(TypedDict):
    """Result of a successful screenshot capture."""

    path: str


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def screenshot() -> ScreenshotResult:
    """Capture StS window, save as JPEG.

    Returns:
        ScreenshotResult with the path to the saved file.

    Raises:
        RuntimeError: if StS window is not found or capture fails.
    """
    # 1. Ensure output dir exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Find StS window
    window = _find_window(WINDOW_TITLE)
    if window is None:
        logger.error("StS window not found", extra={"event": "screenshot_error"})
        msg = "Slay the Spire window not found"
        raise RuntimeError(msg)

    # 3. Capture raw PNG with retry
    raw_bytes = b""
    for attempt in range(MAX_CAPTURE_ATTEMPTS):
        try:
            raw_bytes = _capture_raw(window["id"])
            break
        except Exception:
            logger.debug(
                "capture attempt failed",
                extra={"event": "capture_retry", "attempt": attempt + 1},
            )
            continue
    if not raw_bytes:
        logger.error(
            "capture failed after retries", extra={"event": "screenshot_error"}
        )
        msg = "Failed to capture Slay the Spire"
        raise RuntimeError(msg)

    # 4. Resize via Pillow
    img = Image.open(io.BytesIO(raw_bytes))
    w, h = img.size
    if w > _MAX_SCREENSHOT_DIMENSION or h > _MAX_SCREENSHOT_DIMENSION:
        ratio = _MAX_SCREENSHOT_DIMENSION / max(w, h)
        img = img.resize(  # pyright: ignore[reportUnknownMemberType]
            (int(w * ratio), int(h * ratio)),
            Image.Resampling.LANCZOS,
        )

    # 5. Generate filename — ISO variant with timezone and milliseconds
    #    e.g. 20260508_025632_123_0900.jpg
    now = datetime.now(UTC).astimezone()
    tz = now.strftime("%z").lstrip("+")  # 0900 or -0500
    millis = now.strftime("%f")[:3]  # 3-digit milliseconds
    filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{millis}_{tz}.jpg"
    output_path = OUTPUT_DIR / filename

    img = img.convert("RGB")
    img.save(output_path, format="JPEG", quality=_SCREENSHOT_JPEG_QUALITY)

    # 6. Rotate old files
    _rotate_files()

    logger.info(
        "screenshot saved",
        extra={
            "event": "screenshot",
            "path": str(output_path),
            "orig_dims": f"{w}x{h}",
            "orig_size": len(raw_bytes),
        },
    )

    return {"path": str(output_path)}
