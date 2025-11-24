"""Behavior-focused telemetry analyzer.

Reads the latest movement telemetry JSONL file (or a user-supplied one) and
summarises flee/hunt/search dynamics so we can verify adrenaline usage,
prey acquisition, and overall activity balance.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from math import hypot
from pathlib import Path
from typing import Any, Dict, Optional

TELEMETRY_DIR = Path("logs/telemetry")


def find_latest_movement_file() -> Path:
    candidates = sorted(TELEMETRY_DIR.glob("movement_*.jsonl"))
    if not candidates:
        raise FileNotFoundError("No movement telemetry files found under logs/telemetry")
    return candidates[-1]


def summarise_behaviors(path: Path) -> None:
    stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: defaultdict(float))
    total_samples = 0

    def _increment(behavior: str, key: str, value: float = 1.0) -> None:
        stats[behavior][key] = stats[behavior].get(key, 0.0) + value

    def _record_distance(behavior: str, key: str, value: Optional[float]) -> None:
        if value is None:
            return
        count_key = f"{key}_count"
        sum_key = f"{key}_sum"
        stats[behavior][count_key] = stats[behavior].get(count_key, 0.0) + 1
        stats[behavior][sum_key] = stats[behavior].get(sum_key, 0.0) + value

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                sample = json.loads(line)
            except json.JSONDecodeError:
                continue

            behavior = str(sample.get("behavior", "unknown")).lower()
            total_samples += 1
            _increment(behavior, "count")

            velocity = sample.get("velocity") or (0.0, 0.0)
            speed = float(hypot(velocity[0], velocity[1]))
            _increment(behavior, "speed_sum", speed)

            effort = float(sample.get("effort", 0.0))
            _increment(behavior, "effort_sum", effort)
            if effort > 1.0:
                _increment(behavior, "high_effort")

            thrust = float(sample.get("thrust", 0.0))
            _increment(behavior, "thrust_sum", thrust)

            energy_ratio = float(sample.get("energy_ratio", 0.0))
            _increment(behavior, "energy_ratio_sum", energy_ratio)

            if sample.get("has_food_target"):
                _increment(behavior, "food_target")

            if behavior == "flee":
                _record_distance(behavior, "threat_distance", sample.get("threat_distance"))
            elif behavior == "hunt":
                _record_distance(behavior, "prey_distance", sample.get("prey_distance"))
            elif behavior == "search":
                # Track how often search is triggered without a target
                if not sample.get("has_food_target"):
                    _increment(behavior, "empty_search")

    if total_samples == 0:
        print("No movement samples found in", path)
        return

    print(f"Behavior breakdown from {path.name} ({total_samples} samples):\n")
    header = (
        "Behavior",
        "Share%",
        "AvgSpeed",
        "AvgEffort",
        "HighEffort%",
        "AvgThrust",
        "AvgEnergy",
    )
    print(f"{header[0]:>10s} {header[1]:>8s} {header[2]:>9s} {header[3]:>10s} {header[4]:>12s} {header[5]:>10s} {header[6]:>10s}")
    print("-" * 74)

    for behavior, data in sorted(stats.items(), key=lambda item: -item[1].get("count", 0.0)):
        count = data.get("count", 0.0)
        share = (count / total_samples) * 100
        avg_speed = data.get("speed_sum", 0.0) / max(1.0, count)
        avg_effort = data.get("effort_sum", 0.0) / max(1.0, count)
        high_effort_pct = (data.get("high_effort", 0.0) / max(1.0, count)) * 100
        avg_thrust = data.get("thrust_sum", 0.0) / max(1.0, count)
        avg_energy = data.get("energy_ratio_sum", 0.0) / max(1.0, count)
        print(
            f"{behavior:>10s} {share:8.2f} {avg_speed:9.2f} {avg_effort:10.2f} "
            f"{high_effort_pct:12.2f} {avg_thrust:10.2f} {avg_energy:10.2f}"
        )

        if behavior == "flee":
            td_count = data.get("threat_distance_count", 0.0)
            if td_count:
                avg_td = data.get("threat_distance_sum", 0.0) / td_count
                print(f"    ↳ Avg threat distance: {avg_td:.1f} (n={int(td_count)})")
        elif behavior == "hunt":
            pd_count = data.get("prey_distance_count", 0.0)
            if pd_count:
                avg_pd = data.get("prey_distance_sum", 0.0) / pd_count
                print(f"    ↳ Avg prey distance: {avg_pd:.1f} (n={int(pd_count)})")
        elif behavior == "search":
            empty = data.get("empty_search", 0.0)
            if empty:
                pct = (empty / max(1.0, count)) * 100
                print(f"    ↳ Searches without targets: {pct:.1f}%")

        if data.get("food_target"):
            pct_food = (data.get("food_target", 0.0) / max(1.0, count)) * 100
            print(f"    ↳ Has food target: {pct_food:.1f}% of samples")

    print("\nLegend:")
    print("  AvgSpeed   - Magnitude of velocity vector in px/tick")
    print("  HighEffort - % of frames with effort>1.0 (adrenaline/burst)")
    print("  AvgEnergy  - Current energy ratio (1.0 == full reserves)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarise hunt/flee behavior from movement telemetry")
    parser.add_argument("telemetry", nargs="?", type=Path, help="Path to movement_*.jsonl file")
    args = parser.parse_args()

    path = args.telemetry or find_latest_movement_file()
    summarise_behaviors(path)


if __name__ == "__main__":
    main()

