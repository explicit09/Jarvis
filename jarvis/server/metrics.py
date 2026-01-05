"""Prometheus metrics for J.A.R.V.I.S API."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Try to import prometheus_client
try:
    from prometheus_client import Counter, Histogram, Gauge, CONTENT_TYPE_LATEST, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.info("prometheus_client not installed, metrics disabled")


if PROMETHEUS_AVAILABLE:
    # Request counter
    REQUESTS = Counter(
        "jarvis_requests_total",
        "Total HTTP requests",
        labelnames=("endpoint", "method", "status"),
    )

    # Stage latencies (seconds)
    ASR_LATENCY = Histogram(
        "jarvis_asr_seconds",
        "ASR (speech-to-text) latency in seconds",
        buckets=(0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4),
    )

    LLM_LATENCY = Histogram(
        "jarvis_llm_seconds",
        "LLM processing latency in seconds",
        buckets=(0.1, 0.3, 0.6, 1.0, 2.0, 4.0, 8.0),
    )

    TTS_LATENCY = Histogram(
        "jarvis_tts_seconds",
        "TTS (text-to-speech) latency in seconds",
        buckets=(0.05, 0.1, 0.2, 0.4, 0.8, 1.6),
    )

    E2E_LATENCY = Histogram(
        "jarvis_e2e_seconds",
        "End-to-end request latency in seconds",
        buckets=(0.5, 1.0, 2.0, 4.0, 8.0, 16.0),
    )

    # Tool calls
    TOOL_CALLS = Counter(
        "jarvis_tool_calls_total",
        "Total tool invocations",
        labelnames=("tool", "status"),
    )

    # Service health
    SERVICE_UP = Gauge(
        "jarvis_service_up",
        "Service health (1=up, 0=down)",
        labelnames=("service",),
    )

    def prom_latest() -> tuple[bytes, str]:
        """Generate Prometheus metrics output."""
        return generate_latest(), CONTENT_TYPE_LATEST

else:
    # Stub implementations when prometheus_client is not installed
    class _StubMetric:
        def labels(self, *args, **kwargs):
            return self
        def inc(self, *args, **kwargs):
            pass
        def dec(self, *args, **kwargs):
            pass
        def set(self, *args, **kwargs):
            pass
        def observe(self, *args, **kwargs):
            pass

    REQUESTS = _StubMetric()
    ASR_LATENCY = _StubMetric()
    LLM_LATENCY = _StubMetric()
    TTS_LATENCY = _StubMetric()
    E2E_LATENCY = _StubMetric()
    TOOL_CALLS = _StubMetric()
    SERVICE_UP = _StubMetric()

    def prom_latest() -> tuple[bytes, str]:
        return b"# Prometheus metrics not available\n", "text/plain"
