"""Summarize benchmark results."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Optional

from jarvis.config import config


def _results_path() -> Path:
    path = config.storage.data_dir.expanduser()
    return path / "bench_results.jsonl"


@dataclass
class Aggregates:
    count: int
    avg_latency_ms: float
    tool_auto_pass_rate: Optional[float]
    avg_human_score: Optional[float]
    avg_auto_judge_score: Optional[float]


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Aggregates]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = f"{row.get('provider')}:{row.get('model')}"
        buckets[key].append(row)

    results: dict[str, Aggregates] = {}
    for key, items in buckets.items():
        latencies = [float(i.get("latency_ms_total", 0.0)) for i in items]
        auto_pass_values = [i.get("auto_pass") for i in items if i.get("auto_pass") is not None]
        human_scores = [
            i.get("human_score") for i in items if i.get("human_score") is not None
        ]
        auto_scores = [
            i.get("auto_judge_score") for i in items if i.get("auto_judge_score") is not None
        ]

        tool_rate = None
        if auto_pass_values:
            tool_rate = mean([1.0 if v else 0.0 for v in auto_pass_values])

        human_avg = None
        if human_scores:
            human_avg = mean([float(s) for s in human_scores])

        auto_avg = None
        if auto_scores:
            auto_avg = mean([float(s) for s in auto_scores])

        results[key] = Aggregates(
            count=len(items),
            avg_latency_ms=mean(latencies) if latencies else 0.0,
            tool_auto_pass_rate=tool_rate,
            avg_human_score=human_avg,
            avg_auto_judge_score=auto_avg,
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize J.A.R.V.I.S benchmark results")
    parser.add_argument("--path", help="Path to bench_results.jsonl")
    args = parser.parse_args()

    path = Path(args.path) if args.path else _results_path()
    rows = _load_rows(path)
    if not rows:
        raise SystemExit(f"No results found at {path}")

    agg = _aggregate(rows)
    print(f"Results: {path}")
    for key, stats in sorted(agg.items(), key=lambda item: item[1].avg_latency_ms):
        tool_rate = (
            f"{stats.tool_auto_pass_rate*100:.0f}%"
            if stats.tool_auto_pass_rate is not None
            else "n/a"
        )
        human = f"{stats.avg_human_score:.2f}" if stats.avg_human_score is not None else "n/a"
        auto = (
            f"{stats.avg_auto_judge_score:.2f}"
            if stats.avg_auto_judge_score is not None
            else "n/a"
        )
        print(
            f"- {key}: runs={stats.count} avg_latency={stats.avg_latency_ms:.0f}ms "
            f"tool_pass={tool_rate} human={human} auto={auto}"
        )


if __name__ == "__main__":
    main()
