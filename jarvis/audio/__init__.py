"""Audio processing modules for J.A.R.V.I.S."""

__all__ = []

try:
    from .wake_word import WakeWordDetector
    __all__.append("WakeWordDetector")
except ImportError:
    WakeWordDetector = None  # type: ignore

try:
    from .wake_word_oww import OpenWakeWordDetector
    __all__.append("OpenWakeWordDetector")
except ImportError:
    OpenWakeWordDetector = None  # type: ignore
