from importlib import import_module

from .validate_pydantic import validate_pydantic
from .validate_windows_filename import validate_windows_filename
from .generate_uid import generate_uid


# lazy loading，避免循环依赖
def __getattr__(name: str):
    if name in {"FFprobeInspect", "FFprobeInspectResult"}:
        module = import_module(".media_ffprobe_inspect", __name__)
        return getattr(module, name)
    if name in {"show_confirm_dialog", "show_notify_dialog"}:
        module = import_module(".popup_dialog", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "validate_pydantic",
    "validate_windows_filename",
    "generate_uid",
    "FFprobeInspect", "FFprobeInspectResult",
    "show_confirm_dialog", "show_notify_dialog",
]
