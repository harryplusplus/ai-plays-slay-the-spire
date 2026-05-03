"""macOS window utilities — find & capture Slay the Spire window.

Uses CoreGraphics via ctypes (no external deps).
"""

import base64
import ctypes
import ctypes.util
import io
import logging
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)

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

# --- CoreFoundation / CoreGraphics additions for cross-space capture ---


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
    _msg = "ImageIO framework not found"
    raise RuntimeError(_msg)
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


_CG_WINDOW_OWNER_NAME = _cfstr("kCGWindowOwnerName")
_CG_WINDOW_NAME = _cfstr("kCGWindowName")
_CG_WINDOW_NUMBER = _cfstr("kCGWindowNumber")
_CG_WINDOW_LAYER = _cfstr("kCGWindowLayer")


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


def _find_window(
    title_contains: str = "Modded Slay the Spire",
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


def _capture(window_id: int) -> bytes:
    """Capture a window by id, return raw PNG bytes (cross-space safe).

    Uses CGWindowListCreateImage + ImageIO instead of screencapture(1),
    so it works even when the window is on a different macOS Space.
    """
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


_MAX_SCREENSHOT_DIMENSION = 800
_SCREENSHOT_JPEG_QUALITY = 70


def capture_screenshot() -> str:
    """Capture, resize, and return base64-encoded JPEG.

    Resizes to at most 800px on the longest edge to keep context small.
    Raises on failure — no fallback. Screenshot is mandatory.
    """
    window = _find_window("Modded Slay the Spire")
    if window is None:
        msg = "Slay the Spire window not found"
        raise RuntimeError(msg)
    raw_bytes = b""
    for _ in range(5):
        try:
            raw_bytes = _capture(window["id"])
            break
        except Exception:  # noqa: BLE001, S112
            continue
    if not raw_bytes:
        msg = "Failed to capture StS"
        raise RuntimeError(msg)
    img = Image.open(io.BytesIO(raw_bytes))
    w, h = img.size
    if w > _MAX_SCREENSHOT_DIMENSION or h > _MAX_SCREENSHOT_DIMENSION:
        ratio = _MAX_SCREENSHOT_DIMENSION / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)  # pyright: ignore[reportUnknownMemberType,reportAttributeAccessIssue]
    buf = io.BytesIO()
    img = img.convert("RGB")
    img.save(buf, format="JPEG", quality=_SCREENSHOT_JPEG_QUALITY)
    b64 = base64.b64encode(buf.getvalue()).decode()
    logger.info(
        "screenshot captured",
        extra={
            "event": "screenshot",
            "window_id": window["id"],
            "original_size": len(raw_bytes),
            "resized_size": len(b64),
            "original_dims": f"{w}x{h}",
        },
    )
    return b64


if __name__ == "__main__":
    import tempfile

    b64 = capture_screenshot()
    jpg_bytes = base64.b64decode(b64)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(jpg_bytes)
        tmp_path = tmp.name

    img = Image.open(tmp_path)
    print(f"file://{tmp_path}")
    print(f"size={len(jpg_bytes)} bytes")
    print(f"dims={img.size[0]}x{img.size[1]}")
    print(f"b64={b64[:120]}...")
