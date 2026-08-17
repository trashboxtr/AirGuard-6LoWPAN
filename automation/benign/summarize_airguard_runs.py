#!/usr/bin/env python3
"""Summarize validated AirGuard Cooja logs into one run-level CSV.

The parser uses only Python's standard library and supports both GUI-exported
logs and headless COOJA.testlog formatting because it searches for the
AIRGUARD_* payload inside each line.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

METRIC_PREFIX = "AIRGUARD_METRIC,"
EVENT_PREFIX = "AIRGUARD_EVENT,"
BOOT_PREFIX = "AIRGUARD_BOOT,"
AUTO_STARTED_PREFIX = "AIRGUARD_AUTOMATION,status=started,"
AUTO_COMPLETE_PREFIX = "AIRGUARD_AUTOMATION,status=complete,"


@dataclass
class ParsedRecord:
    kind: str
    fields: dict[str, str]


def parse_payload(line: str) -> ParsedRecord | None:
    for prefix, kind in (
        (METRIC_PREFIX, "metric"),
        (EVENT_PREFIX, "event"),
        (BOOT_PREFIX, "boot"),
        (AUTO_STARTED_PREFIX, "automation_started"),
        (AUTO_COMPLETE_PREFIX, "automation_complete"),
    ):
        pos = line.find(prefix)
        if pos < 0:
            continue
        payload = line[pos:].strip()
        parts = payload.split(",")
        fields: dict[str, str] = {}
        if kind == "event" and len(parts) > 1 and parts[1].startswith("event="):
            fields["event"] = parts[1].split("=", 1)[1]
        for token in parts[1:]:
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            fields[key.strip()] = value.strip()
        return ParsedRecord(kind=kind, fields=fields)
    return None


def to_int(value: str | None, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value: str | None, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def read_metadata(log_path: Path) -> dict[str, object]:
    metadata_path = log_path.with_suffix(".metadata.json")
    if metadata_path.is_file():
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    return {}


def select_metric_at_or_before(metrics: list[dict[str, str]], target_ms: int) -> dict[str, str] | None:
    candidates = [m for m in metrics if (to_int(m.get("time_ms"), -1) or -1) <= target_ms]
    if not candidates:
        return None
    return max(candidates, key=lambda m: to_int(m.get("time_ms"), -1) or -1)


def final_metric_by_node(metrics_by_node: dict[int, list[dict[str, str]]], duration_ms: int) -> dict[int, dict[str, str]]:
    result: dict[int, dict[str, str]] = {}
    for node, metrics in metrics_by_node.items():
        at_or_before = select_metric_at_or_before(metrics, duration_ms + 1000)
        if at_or_before is not None:
            result[node] = at_or_before
    return result


def safe_ratio(numerator: int | float | None, denominator: int | float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def fmt_optional(value: float | int | str | None) -> object:
    if value is None:
        return ""
    if isinstance(value, float):
        return round(value, 6)
    return value


def infer_scenario_from_name(name: str) -> str:
    for scenario in ("Clean", "RX90", "RX75", "RX60"):
        if scenario.lower() in name.lower():
            return scenario
    return "unknown"


def infer_seed_from_name(name: str) -> int | None:
    match = re.search(r"seed(\d+)", name, re.IGNORECASE)
    return int(match.group(1)) if match else None


def summarize_log(log_path: Path, default_duration_s: int, default_warmup_s: int) -> dict[str, object]:
    metadata = read_metadata(log_path)
    scenario = str(metadata.get("scenario") or infer_scenario_from_name(log_path.name))
    seed = metadata.get("seed")
    if seed is None:
        seed = infer_seed_from_name(log_path.name)

    duration_s = int(metadata.get("duration_s") or default_duration_s)
    warmup_s = int(metadata.get("warmup_s") or default_warmup_s)
    duration_ms = duration_s * 1000
    warmup_ms = warmup_s * 1000

    metrics_by_node: dict[int, list[dict[str, str]]] = defaultdict(list)
    boot_nodes: set[int] = set()
    automation_complete = False
    rtts_all: list[float] = []
    rtts_analysis: list[float] = []
    app_tx_by_key: dict[tuple[int, int], int] = {}
    app_rx_by_key: dict[tuple[int, int], tuple[int, float | None]] = {}
    parent_change_events: list[dict[str, str]] = []
    app_tx_events = 0
    app_rx_events = 0
    server_rx_events = 0
    server_tx_events = 0
    invalid_payload_events = 0

    with log_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            record = parse_payload(line)
            if record is None:
                continue
            fields = record.fields
            if record.kind == "boot":
                node = to_int(fields.get("node"))
                if node is not None:
                    boot_nodes.add(node)
            elif record.kind == "automation_complete":
                automation_complete = True
            elif record.kind == "metric":
                node = to_int(fields.get("node"))
                if node is not None:
                    metrics_by_node[node].append(fields)
            elif record.kind == "event":
                event = fields.get("event", "")
                event_time = to_int(fields.get("time_ms"), -1) or -1
                if event == "app_tx":
                    app_tx_events += 1
                    node = to_int(fields.get("node"))
                    seq = to_int(fields.get("seq"))
                    if node is not None and seq is not None:
                        app_tx_by_key[(node, seq)] = event_time
                elif event == "app_rx":
                    app_rx_events += 1
                    node = to_int(fields.get("node"))
                    seq = to_int(fields.get("seq"))
                    rtt = to_float(fields.get("rtt_ms"))
                    if node is not None and seq is not None:
                        app_rx_by_key[(node, seq)] = (event_time, rtt)
                elif event == "server_rx":
                    server_rx_events += 1
                    if to_int(fields.get("payload_ok"), 1) == 0:
                        invalid_payload_events += 1
                elif event == "server_tx":
                    server_tx_events += 1
                elif event == "parent_change":
                    parent_change_events.append(fields)

    # Pair application transactions by (node, sequence). The logger keeps a
    # 10-second grace period after the nominal duration, so a request sent just
    # before the analysis cutoff can still be credited when its response arrives
    # shortly after the cutoff.
    eligible_all_keys = {
        key for key, tx_time in app_tx_by_key.items()
        if 0 <= tx_time <= duration_ms
    }
    eligible_analysis_keys = {
        key for key, tx_time in app_tx_by_key.items()
        if warmup_ms <= tx_time <= duration_ms
    }
    matched_all_keys = eligible_all_keys.intersection(app_rx_by_key)
    matched_analysis_keys = eligible_analysis_keys.intersection(app_rx_by_key)
    rtts_all = [
        app_rx_by_key[key][1]
        for key in matched_all_keys
        if app_rx_by_key[key][1] is not None
    ]
    rtts_analysis = [
        app_rx_by_key[key][1]
        for key in matched_analysis_keys
        if app_rx_by_key[key][1] is not None
    ]

    final_by_node = final_metric_by_node(metrics_by_node, duration_ms)
    warmup_by_node: dict[int, dict[str, str]] = {}
    for node, metrics in metrics_by_node.items():
        metric = select_metric_at_or_before(metrics, warmup_ms + 1000)
        if metric is not None:
            warmup_by_node[node] = metric

    client_final = [m for node, m in final_by_node.items() if node != 1 and m.get("role") == "client"]
    server_final = final_by_node.get(1)

    client_app_tx = sum(to_int(m.get("app_tx"), 0) or 0 for m in client_final)
    client_app_rx = sum(to_int(m.get("app_rx"), 0) or 0 for m in client_final)
    client_timeouts = sum(to_int(m.get("app_timeouts"), 0) or 0 for m in client_final)
    route_miss = sum(to_int(m.get("route_miss"), 0) or 0 for m in client_final)
    queue_drops_clients = sum(to_int(m.get("queue_drops"), 0) or 0 for m in client_final)
    reachable_clients = sum(1 for m in client_final if to_int(m.get("reachable"), 0) == 1)

    etx_values = [
        float(to_int(m.get("etx_x100"), -1) or -1)
        for m in client_final
        if (to_int(m.get("etx_x100"), -1) or -1) >= 0
    ]
    ranks = [
        float(to_int(m.get("rank"), -1) or -1)
        for m in client_final
        if 0 < (to_int(m.get("rank"), -1) or -1) < 65535
    ]

    client_mac_attempts = sum(to_int(m.get("mac_tx_attempts"), 0) or 0 for m in client_final)
    client_mac_acked = sum(to_int(m.get("mac_acked"), 0) or 0 for m in client_final)
    client_mac_rx = sum(to_int(m.get("mac_rx"), 0) or 0 for m in client_final)

    server_mac_attempts = to_int(server_final.get("mac_tx_attempts"), 0) if server_final else 0
    server_mac_acked = to_int(server_final.get("mac_acked"), 0) if server_final else 0
    server_mac_rx = to_int(server_final.get("mac_rx"), 0) if server_final else 0
    server_rx = to_int(server_final.get("server_rx"), 0) if server_final else 0
    server_tx = to_int(server_final.get("server_tx"), 0) if server_final else 0

    extra_parent_changes = sum(
        max((to_int(m.get("parent_changes"), 0) or 0) - 1, 0)
        for m in client_final
    )

    energest_tx_final = sum(to_int(m.get("energest_tx"), 0) or 0 for m in client_final)
    energest_tx_warmup = sum(
        to_int(warmup_by_node.get(node, {}).get("energest_tx"), 0) or 0
        for node in range(2, 17)
    )
    energest_tx_analysis_delta = energest_tx_final - energest_tx_warmup

    metadata_validation = metadata.get("validation", {}) if isinstance(metadata, dict) else {}
    valid_from_metadata = metadata_validation.get("valid") if isinstance(metadata_validation, dict) else None

    row: dict[str, object] = {
        "log_file": str(log_path),
        "scenario": scenario,
        "seed": seed if seed is not None else "",
        "duration_s": duration_s,
        "warmup_s": warmup_s,
        "analysis_s": duration_s - warmup_s,
        "boot_count": len(boot_nodes),
        "metric_nodes_final": len(final_by_node),
        "reachable_clients_final": reachable_clients,
        "client_app_tx_final": client_app_tx,
        "client_app_rx_final": client_app_rx,
        "app_delivery_ratio_final": fmt_optional(safe_ratio(client_app_rx, client_app_tx)),
        "client_timeouts_final": client_timeouts,
        "route_miss_final": route_miss,
        "server_rx_final": server_rx,
        "server_tx_final": server_tx,
        "event_app_tx_count": app_tx_events,
        "event_app_rx_count": app_rx_events,
        "event_server_rx_count": server_rx_events,
        "event_server_tx_count": server_tx_events,
        "eligible_app_tx_all": len(eligible_all_keys),
        "matched_app_rx_all": len(matched_all_keys),
        "event_delivery_ratio_all": fmt_optional(safe_ratio(len(matched_all_keys), len(eligible_all_keys))),
        "eligible_app_tx_analysis": len(eligible_analysis_keys),
        "matched_app_rx_analysis": len(matched_analysis_keys),
        "event_delivery_ratio_analysis": fmt_optional(safe_ratio(len(matched_analysis_keys), len(eligible_analysis_keys))),
        "invalid_payload_events": invalid_payload_events,
        "rtt_count_all": len(rtts_all),
        "rtt_mean_ms_all": fmt_optional(statistics.fmean(rtts_all) if rtts_all else None),
        "rtt_median_ms_all": fmt_optional(statistics.median(rtts_all) if rtts_all else None),
        "rtt_p95_ms_all": fmt_optional(percentile(rtts_all, 0.95)),
        "rtt_max_ms_all": fmt_optional(max(rtts_all) if rtts_all else None),
        "rtt_count_analysis": len(rtts_analysis),
        "rtt_mean_ms_analysis": fmt_optional(statistics.fmean(rtts_analysis) if rtts_analysis else None),
        "rtt_median_ms_analysis": fmt_optional(statistics.median(rtts_analysis) if rtts_analysis else None),
        "rtt_p95_ms_analysis": fmt_optional(percentile(rtts_analysis, 0.95)),
        "rtt_max_ms_analysis": fmt_optional(max(rtts_analysis) if rtts_analysis else None),
        "mean_etx_x100_final": fmt_optional(statistics.fmean(etx_values) if etx_values else None),
        "mean_rank_final": fmt_optional(statistics.fmean(ranks) if ranks else None),
        "client_mac_tx_attempts_final": client_mac_attempts,
        "client_mac_acked_final": client_mac_acked,
        "client_mac_ack_ratio_final": fmt_optional(safe_ratio(client_mac_acked, client_mac_attempts)),
        "client_mac_rx_final": client_mac_rx,
        "server_mac_tx_attempts_final": server_mac_attempts,
        "server_mac_acked_final": server_mac_acked,
        "server_mac_ack_ratio_final": fmt_optional(safe_ratio(server_mac_acked, server_mac_attempts)),
        "server_mac_rx_final": server_mac_rx,
        "queue_drops_clients_final": queue_drops_clients,
        "extra_parent_changes_final": extra_parent_changes,
        "parent_change_event_count": len(parent_change_events),
        "client_energest_tx_final": energest_tx_final,
        "client_energest_tx_warmup": energest_tx_warmup,
        "client_energest_tx_analysis_delta": energest_tx_analysis_delta,
        "automation_complete_marker": automation_complete,
        "metadata_valid": valid_from_metadata if valid_from_metadata is not None else "",
    }
    return row


def find_logs(log_root: Path) -> list[Path]:
    return sorted(path for path in log_root.rglob("*.log") if path.is_file())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AirGuard koşu loglarını run-level CSV'ye özetle")
    parser.add_argument(
        "--log-root",
        type=Path,
        default=Path("/home/ubuntu/AirGuard-6LoWPAN/raw-data/mote-logs/cross-layer-v1_1/final-600s"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/home/ubuntu/AirGuard-6LoWPAN/processed-data/run-level/AirGuard_run_summary.csv"),
    )
    parser.add_argument("--duration", type=int, default=600, help="Metadata yoksa kullanılacak süre")
    parser.add_argument("--warmup", type=int, default=120, help="Metadata yoksa kullanılacak warm-up")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    log_root = args.log_root.resolve()
    output = args.output.resolve()

    if not log_root.is_dir():
        print(f"HATA: Log klasörü bulunamadı: {log_root}")
        return 1

    logs = find_logs(log_root)
    if not logs:
        print(f"HATA: .log dosyası bulunamadı: {log_root}")
        return 1

    rows = [summarize_log(path, args.duration, args.warmup) for path in logs]
    rows.sort(key=lambda row: (str(row["scenario"]), int(row["seed"]) if row["seed"] != "" else -1))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Özetlenen log sayısı: {len(rows)}")
    print(f"Çıktı: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
