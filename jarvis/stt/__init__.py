"""Speech-to-Text modules for J.A.R.V.I.S."""

from .hybrid import HybridSTT
from .fallback import FallbackASR, ASRBackend, ASRResult, get_fallback_asr

__all__ = ["HybridSTT", "FallbackASR", "ASRBackend", "ASRResult", "get_fallback_asr"]
