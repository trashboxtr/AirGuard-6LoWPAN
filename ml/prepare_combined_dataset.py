#!/usr/bin/env python3
"""
AirGuard-6LoWPAN unified dataset builder.

Reads:
- 40 Clean/RX impairment runs
- 30 UDP/DIS/DIO attack runs

Builds leakage-safe, 10-second network- and node-window datasets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


BENIGN_SCENARIOS = ("Clean", "RX90", "RX75", "RX60")
ATTACK_SCENARIOS = ("UDP_Flood", "DIS_Flood", "DIO_Flood")
ALL_SCENARIOS = BENIGN_SCENARIOS + ATTACK_SCENARIOS

RX_SUCCESS = {
    "Clean": 1.00,
    "RX90": 0.90,
    "RX75": 0.75,
    "RX60": 0.60,
    "UDP_Flood": 1.00,
    "DIS_Flood": 1.00,
    "DIO_Flood": 1.00,
}

EXPECTED_SEEDS = tuple(range(1001, 1011))

LEAKAGE_COLUMNS = {
    "run_id",
    "scenario",
    "seed",
    "window_start_s",
    "window_end_s",
    "binary_label",
    "cause_family",
    "cause_label",
    "attack_subtype",
    "impairment_level",
    "phase",
    "rx_success",
    "is_attack",
    "is_impairment",
    "attack_mode",
    "attack_active",
    "attack_tx",
    "attack_udp_rx",
    "attack_name",
    "attack_node",
}

FEATURE_GROUPS = {
    "application_qos": [
        "reachable_fraction",
        "app_tx_delta",
        "app_rx_delta",
        "app_timeouts_delta",
        "route_miss_delta",
        "root_server_rx_delta",
        "root_server_tx_delta",
        "transaction_count",
        "transaction_success_count",
        "uplink_success_count",
        "app_delivery_ratio",
        "uplink_delivery_ratio",
        "mean_rtt_ms",
        "median_rtt_ms",
        "p95_rtt_ms",
        "max_rtt_ms",
        "std_rtt_ms",
    ],
    "routing": [
        "mean_etx_x100",
        "std_etx_x100",
        "p95_etx_x100",
        "mean_rank",
        "mean_neighbors",
        "mean_rssi",
        "parent_changes_delta",
        "root_mean_etx_x100",
        "root_mean_rssi",
    ],
    "mac": [
        "queue_drops_delta",
        "client_mac_tx_attempts_delta",
        "client_mac_acked_delta",
        "client_mac_rx_delta",
        "client_mac_ack_ratio",
        "client_mac_valid_nodes",
        "client_mac_reset_nodes",
        "root_mac_tx_attempts_delta",
        "root_mac_acked_delta",
        "root_mac_rx_delta",
        "root_mac_ack_ratio",
    ],
    "radio": [
        "client_energest_tx_delta",
        "client_energest_listen_delta",
        "client_energest_total_delta",
        "client_radio_tx_fraction",
        "root_energest_tx_delta",
        "root_radio_tx_fraction",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--benign-root",
        type=Path,
        default=Path("raw-data/mote-logs/cross-layer-v1_1/final-600s"),
    )
    parser.add_argument(
        "--attack-root",
        type=Path,
        default=Path("raw-data/mote-logs/attack-v1_0/attack-final-600s"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("experiments/ml/processed"),
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Development/pilot mode: do not require 70 runs.",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_kv(payload: str) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for token in payload.strip().split(","):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        key = key.strip()
        value = value.strip()
        if re.fullmatch(r"-?\d+", value):
            output[key] = int(value)
        elif re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)", value):
            output[key] = float(value)
        else:
            output[key] = value
    return output


def classify_scenario(scenario: str) -> dict[str, Any]:
    if scenario == "Clean":
        family = "normal"
        impairment = "none"
        attack_subtype = "none"
    elif scenario in {"RX90", "RX75", "RX60"}:
        family = "impairment"
        impairment = scenario.lower()
        attack_subtype = "none"
    elif scenario in ATTACK_SCENARIOS:
        family = "attack"
        impairment = "none"
        attack_subtype = scenario.lower()
    else:
        raise ValueError(f"Unknown scenario: {scenario}")

    return {
        "binary_label": "attack" if family == "attack" else "benign",
        "cause_family": family,
        "cause_label": scenario,
        "attack_subtype": attack_subtype,
        "impairment_level": impairment,
        "is_attack": int(family == "attack"),
        "is_impairment": int(family == "impairment"),
    }


def phase_for_window(scenario: str, start_s: int, end_s: int) -> str:
    if scenario not in ATTACK_SCENARIOS:
        return "steady_nonattack"
    if start_s >= 120 and end_s <= 170:
        return "pre_attack"
    if start_s >= 170 and end_s <= 190:
        return "attack_start_transition"
    if start_s >= 190 and end_s <= 530:
        return "attack_active_core"
    if start_s >= 530 and end_s <= 550:
        return "attack_stop_transition"
    if start_s >= 550 and end_s <= 600:
        return "recovery"
    return "other"


def discover_logs(root: Path, scenarios: tuple[str, ...]) -> list[Path]:
    logs: list[Path] = []
    for scenario in scenarios:
        scenario_dir = root / scenario
        if scenario_dir.is_dir():
            logs.extend(sorted(scenario_dir.glob("*.log")))
    return logs


def read_run(log_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scenario = log_path.parent.name
    match = re.search(r"seed(\d+)", log_path.name)
    if not match:
        raise ValueError(f"Seed missing from filename: {log_path}")
    seed = int(match.group(1))

    metadata_path = log_path.with_suffix(".metadata.json")
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Metadata missing: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    text = log_path.read_text(encoding="utf-8", errors="replace")
    actual_sha = sha256_file(log_path)
    expected_sha = metadata.get("output_log_sha256")
    validation = metadata.get("validation", {})

    random_seed_match = re.search(r"^Random seed:\s*(\d+)", text, re.MULTILINE)
    random_seed = int(random_seed_match.group(1)) if random_seed_match else None

    integrity = {
        "run_id": metadata.get("run_id", f"{scenario}_seed{seed}_600s"),
        "scenario": scenario,
        "seed": seed,
        "metadata_valid": bool(validation.get("valid", False)),
        "boot_count": int(validation.get("boot_count", 0)),
        "final_metric_count": int(validation.get("final_metric_count", 0)),
        "complete_marker": "AIRGUARD_AUTOMATION,status=complete" in text,
        "test_ok": "TEST OK" in text,
        "sha256_matches_metadata": bool(expected_sha and expected_sha == actual_sha),
        "random_seed_in_log": random_seed,
        "random_seed_matches": random_seed == seed,
        "log_sha256": actual_sha,
        "wall_elapsed_s": metadata.get("wall_elapsed_s"),
    }

    rows: list[dict[str, Any]] = []
    line_prefix = re.compile(r"^(\d+)\s+(\d+)\s+\[")

    markers = (
        ("AIRGUARD_BOOT,", "boot"),
        ("AIRGUARD_EVENT,", "event"),
        ("AIRGUARD_METRIC,", "metric"),
        ("AIRGUARD_ATTACK,", "attack"),
    )

    for line in text.splitlines():
        prefix = line_prefix.match(line)
        global_us = int(prefix.group(1)) if prefix else None
        mote_id = int(prefix.group(2)) if prefix else None

        for marker, kind in markers:
            if marker not in line:
                continue
            row = {
                "run_id": integrity["run_id"],
                "scenario": scenario,
                "seed": seed,
                "global_us": global_us,
                "global_s": global_us / 1_000_000 if global_us is not None else np.nan,
                "mote_id": mote_id,
                "kind": kind,
            }
            row.update(parse_kv(line.split(marker, 1)[1]))
            rows.append(row)
            break

    return rows, integrity


def numericize(frame: pd.DataFrame) -> pd.DataFrame:
    numeric_columns = [
        "node",
        "seq",
        "time_ms",
        "reachable",
        "rank",
        "parent_id",
        "parent_changes",
        "neighbors",
        "etx_x100",
        "rssi",
        "app_tx",
        "app_rx",
        "app_timeouts",
        "route_miss",
        "pending",
        "last_rtt_ms",
        "mac_tx_attempts",
        "mac_acked",
        "mac_rx",
        "queue_drops",
        "energest_tx",
        "energest_listen",
        "energest_total",
        "server_rx",
        "server_tx",
        "mean_etx_x100",
        "mean_rssi",
        "old_parent_id",
        "new_parent_id",
        "rtt_ms",
        "payload_ok",
        "src_node",
        "dst_node",
        "attack_mode",
        "attack_active",
        "attack_tx",
        "attack_udp_rx",
    ]
    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def build_transactions(events: pd.DataFrame) -> pd.DataFrame:
    key = ["run_id", "scenario", "seed", "node", "seq"]

    tx = events[events.get("event").eq("app_tx")][
        ["run_id", "scenario", "seed", "node", "seq", "global_s", "time_ms"]
    ].rename(columns={"global_s": "tx_global_s", "time_ms": "tx_local_ms"})

    rx = events[events.get("event").eq("app_rx")][
        ["run_id", "scenario", "seed", "node", "seq", "global_s", "time_ms", "rtt_ms", "payload_ok"]
    ].rename(columns={"global_s": "rx_global_s", "time_ms": "rx_local_ms"})

    server_rx = events[events.get("event").eq("server_rx")][
        ["run_id", "scenario", "seed", "src_node", "seq", "global_s", "payload_ok"]
    ].rename(
        columns={
            "src_node": "node",
            "global_s": "server_rx_global_s",
            "payload_ok": "server_payload_ok",
        }
    )

    server_tx = events[events.get("event").eq("server_tx")][
        ["run_id", "scenario", "seed", "dst_node", "seq", "global_s"]
    ].rename(columns={"dst_node": "node", "global_s": "server_tx_global_s"})

    timeout = events[events.get("event").eq("app_timeout")][
        ["run_id", "scenario", "seed", "node", "seq", "global_s"]
    ].rename(columns={"global_s": "timeout_global_s"})

    eligible_tx = tx[(tx["tx_global_s"] >= 120) & (tx["tx_global_s"] < 600)].copy()

    def first_per_key(frame: pd.DataFrame, time_column: str) -> pd.DataFrame:
        if frame.empty:
            return frame
        return frame.sort_values(time_column).groupby(key, as_index=False).first()

    rx_first = first_per_key(rx[(rx["rx_global_s"] <= 610) & (rx["rtt_ms"] >= 0)], "rx_global_s")
    server_rx_first = first_per_key(server_rx[server_rx["server_rx_global_s"] <= 610], "server_rx_global_s")
    server_tx_first = first_per_key(server_tx[server_tx["server_tx_global_s"] <= 610], "server_tx_global_s")
    timeout_first = first_per_key(timeout[timeout["timeout_global_s"] <= 610], "timeout_global_s")

    transactions = eligible_tx.merge(rx_first, on=key, how="left")
    transactions = transactions.merge(server_rx_first, on=key, how="left")
    transactions = transactions.merge(server_tx_first, on=key, how="left")
    transactions = transactions.merge(timeout_first, on=key, how="left")

    transactions["transaction_success"] = transactions["rx_global_s"].notna().astype(int)
    transactions["uplink_success"] = transactions["server_rx_global_s"].notna().astype(int)
    transactions["downlink_sent"] = transactions["server_tx_global_s"].notna().astype(int)
    transactions["timeout_observed"] = transactions["timeout_global_s"].notna().astype(int)

    transactions["window_start_s"] = (
        np.floor(transactions["tx_global_s"] / 10) * 10
    ).astype(int)
    transactions["window_end_s"] = transactions["window_start_s"] + 10

    labels = transactions["scenario"].map(classify_scenario)
    label_frame = pd.DataFrame(labels.tolist(), index=transactions.index)
    transactions = pd.concat([transactions, label_frame], axis=1)

    return transactions


def build_node_windows(metrics: pd.DataFrame) -> pd.DataFrame:
    output: list[dict[str, Any]] = []

    for (run_id, scenario, seed, node), group in metrics.groupby(
        ["run_id", "scenario", "seed", "node"]
    ):
        group = group.sort_values("time_ms").copy()
        role = str(group["role"].iloc[0])
        selected = group[(group["time_ms"] >= 120000) & (group["time_ms"] <= 600010)]

        previous = None
        for _, current in selected.iterrows():
            if previous is None:
                previous = current
                continue

            window_end_s = int(round(float(current["time_ms"]) / 1000.0))
            window_start_s = window_end_s - 10
            parent_changed = int(
                role == "client"
                and (
                    current.get("parent_id") != previous.get("parent_id")
                    or current.get("parent_changes") != previous.get("parent_changes")
                )
            )

            row: dict[str, Any] = {
                "run_id": run_id,
                "scenario": scenario,
                "seed": int(seed),
                "node": int(node),
                "role": role,
                "window_start_s": window_start_s,
                "window_end_s": window_end_s,
                "reachable": current.get("reachable"),
                "rank": current.get("rank"),
                "parent_id": current.get("parent_id"),
                "neighbors": current.get("neighbors"),
                "etx_x100": current.get("etx_x100"),
                "rssi": current.get("rssi"),
                "parent_changed": parent_changed,
                "phase": phase_for_window(scenario, window_start_s, window_end_s),
                "rx_success": RX_SUCCESS[scenario],
            }
            row.update(classify_scenario(scenario))

            cumulative = [
                "app_tx",
                "app_rx",
                "app_timeouts",
                "route_miss",
                "parent_changes",
                "server_rx",
                "server_tx",
                "queue_drops",
                "energest_tx",
                "energest_listen",
                "energest_total",
            ]
            for column in cumulative:
                current_value = current.get(column)
                previous_value = previous.get(column)
                if pd.notna(current_value) and pd.notna(previous_value):
                    row[f"{column}_delta"] = float(current_value - previous_value)
                else:
                    row[f"{column}_delta"] = np.nan

            mac_reset = 0
            for column in ("mac_tx_attempts", "mac_acked", "mac_rx"):
                current_value = current.get(column)
                previous_value = previous.get(column)
                if pd.isna(current_value) or pd.isna(previous_value):
                    row[f"{column}_delta"] = np.nan
                    continue

                delta = float(current_value - previous_value)
                if role == "client" and parent_changed:
                    row[f"{column}_delta"] = np.nan
                    mac_reset = 1
                elif delta < 0:
                    row[f"{column}_delta"] = np.nan
                    mac_reset = 1
                else:
                    row[f"{column}_delta"] = delta

            row["mac_counter_reset"] = mac_reset
            row["server_mean_etx_x100"] = (
                current.get("mean_etx_x100") if role == "server" else np.nan
            )
            row["server_mean_rssi"] = (
                current.get("mean_rssi") if role == "server" else np.nan
            )
            output.append(row)
            previous = current

    return pd.DataFrame(output)


def aggregate_transaction_windows(transactions: pd.DataFrame) -> pd.DataFrame:
    if transactions.empty:
        return pd.DataFrame()

    grouped = transactions.groupby(
        ["run_id", "scenario", "seed", "window_start_s", "window_end_s"],
        as_index=False,
    ).agg(
        transaction_count=("seq", "size"),
        transaction_success_count=("transaction_success", "sum"),
        uplink_success_count=("uplink_success", "sum"),
        timeout_event_count=("timeout_observed", "sum"),
        mean_rtt_ms=("rtt_ms", "mean"),
        median_rtt_ms=("rtt_ms", "median"),
        p95_rtt_ms=("rtt_ms", lambda values: float(np.nanpercentile(values, 95))),
        max_rtt_ms=("rtt_ms", "max"),
        std_rtt_ms=("rtt_ms", "std"),
    )
    grouped["app_delivery_ratio"] = (
        grouped["transaction_success_count"] / grouped["transaction_count"]
    )
    grouped["uplink_delivery_ratio"] = (
        grouped["uplink_success_count"] / grouped["transaction_count"]
    )
    grouped["std_rtt_ms"] = grouped["std_rtt_ms"].fillna(0.0)
    return grouped


def build_network_windows(
    node_windows: pd.DataFrame,
    transaction_windows: pd.DataFrame,
) -> pd.DataFrame:
    output: list[dict[str, Any]] = []

    group_columns = ["run_id", "scenario", "seed", "window_start_s", "window_end_s"]
    for keys, group in node_windows.groupby(group_columns):
        run_id, scenario, seed, start_s, end_s = keys
        clients = group[group["role"] == "client"].copy()
        root = group[group["role"] == "server"].copy()

        valid_etx = clients[(clients["reachable"] == 1) & (clients["etx_x100"] >= 0)]
        valid_rank = clients[
            (clients["reachable"] == 1)
            & (clients["rank"] > 0)
            & (clients["rank"] < 65535)
        ]

        client_attempts = clients["mac_tx_attempts_delta"].sum(min_count=1)
        client_acked = clients["mac_acked_delta"].sum(min_count=1)
        root_row = root.iloc[0] if len(root) else pd.Series(dtype=float)

        row: dict[str, Any] = {
            "run_id": run_id,
            "scenario": scenario,
            "seed": int(seed),
            "window_start_s": int(start_s),
            "window_end_s": int(end_s),
            "phase": phase_for_window(scenario, int(start_s), int(end_s)),
            "rx_success": RX_SUCCESS[scenario],
            "reachable_fraction": float(clients["reachable"].mean()),
            "mean_etx_x100": float(valid_etx["etx_x100"].mean()) if len(valid_etx) else np.nan,
            "std_etx_x100": float(valid_etx["etx_x100"].std(ddof=1)) if len(valid_etx) > 1 else 0.0,
            "p95_etx_x100": float(np.percentile(valid_etx["etx_x100"], 95)) if len(valid_etx) else np.nan,
            "mean_rank": float(valid_rank["rank"].mean()) if len(valid_rank) else np.nan,
            "mean_neighbors": float(clients["neighbors"].mean()),
            "mean_rssi": float(valid_etx["rssi"].mean()) if len(valid_etx) else np.nan,
            "app_tx_delta": float(clients["app_tx_delta"].sum()),
            "app_rx_delta": float(clients["app_rx_delta"].sum()),
            "app_timeouts_delta": float(clients["app_timeouts_delta"].sum()),
            "route_miss_delta": float(clients["route_miss_delta"].sum()),
            "parent_changes_delta": float(clients["parent_changes_delta"].sum()),
            "queue_drops_delta": float(clients["queue_drops_delta"].sum()),
            "client_mac_tx_attempts_delta": client_attempts,
            "client_mac_acked_delta": client_acked,
            "client_mac_rx_delta": clients["mac_rx_delta"].sum(min_count=1),
            "client_mac_ack_ratio": (
                float(client_acked / client_attempts)
                if pd.notna(client_attempts) and client_attempts > 0
                else np.nan
            ),
            "client_mac_valid_nodes": int(clients["mac_tx_attempts_delta"].notna().sum()),
            "client_mac_reset_nodes": int(clients["mac_counter_reset"].sum()),
            "client_energest_tx_delta": float(clients["energest_tx_delta"].sum()),
            "client_energest_listen_delta": float(clients["energest_listen_delta"].sum()),
            "client_energest_total_delta": float(clients["energest_total_delta"].sum()),
            "client_radio_tx_fraction": (
                float(
                    clients["energest_tx_delta"].sum()
                    / clients["energest_total_delta"].sum()
                )
                if clients["energest_total_delta"].sum() > 0
                else np.nan
            ),
            "root_server_rx_delta": root_row.get("server_rx_delta", np.nan),
            "root_server_tx_delta": root_row.get("server_tx_delta", np.nan),
            "root_mac_tx_attempts_delta": root_row.get("mac_tx_attempts_delta", np.nan),
            "root_mac_acked_delta": root_row.get("mac_acked_delta", np.nan),
            "root_mac_rx_delta": root_row.get("mac_rx_delta", np.nan),
            "root_mac_ack_ratio": (
                float(
                    root_row.get("mac_acked_delta")
                    / root_row.get("mac_tx_attempts_delta")
                )
                if pd.notna(root_row.get("mac_tx_attempts_delta"))
                and root_row.get("mac_tx_attempts_delta") > 0
                else np.nan
            ),
            "root_energest_tx_delta": root_row.get("energest_tx_delta", np.nan),
            "root_radio_tx_fraction": (
                float(
                    root_row.get("energest_tx_delta")
                    / root_row.get("energest_total_delta")
                )
                if pd.notna(root_row.get("energest_total_delta"))
                and root_row.get("energest_total_delta") > 0
                else np.nan
            ),
            "root_mean_etx_x100": root_row.get("server_mean_etx_x100", np.nan),
            "root_mean_rssi": root_row.get("server_mean_rssi", np.nan),
        }
        row.update(classify_scenario(scenario))
        output.append(row)

    network = pd.DataFrame(output)

    if not transaction_windows.empty:
        network = network.merge(
            transaction_windows,
            on=[
                "run_id",
                "scenario",
                "seed",
                "window_start_s",
                "window_end_s",
            ],
            how="left",
        )

    transaction_defaults = {
        "transaction_count": 0,
        "transaction_success_count": 0,
        "uplink_success_count": 0,
        "timeout_event_count": 0,
        "app_delivery_ratio": np.nan,
        "uplink_delivery_ratio": np.nan,
        "mean_rtt_ms": np.nan,
        "median_rtt_ms": np.nan,
        "p95_rtt_ms": np.nan,
        "max_rtt_ms": np.nan,
        "std_rtt_ms": np.nan,
    }
    for column, default in transaction_defaults.items():
        if column not in network:
            network[column] = default
        else:
            network[column] = network[column].fillna(default)

    return network


def validate_expected_runs(integrity: pd.DataFrame, allow_partial: bool) -> None:
    invalid = integrity[
        ~(
            integrity["metadata_valid"]
            & integrity["complete_marker"]
            & integrity["test_ok"]
            & integrity["sha256_matches_metadata"]
            & integrity["random_seed_matches"]
            & integrity["boot_count"].eq(16)
            & integrity["final_metric_count"].eq(16)
        )
    ]
    if len(invalid):
        print(invalid.to_string(index=False))
        raise RuntimeError(f"{len(invalid)} invalid runs found.")

    counts = integrity.groupby("scenario")["run_id"].nunique().to_dict()
    print("Run counts:")
    for scenario in ALL_SCENARIOS:
        print(f"  {scenario}: {counts.get(scenario, 0)}")

    if allow_partial:
        return

    expected = {scenario: 10 for scenario in ALL_SCENARIOS}
    if counts != expected:
        raise RuntimeError(f"Expected 10 runs per scenario, found: {counts}")

    for scenario in ALL_SCENARIOS:
        found = set(
            integrity.loc[integrity["scenario"].eq(scenario), "seed"].astype(int)
        )
        if found != set(EXPECTED_SEEDS):
            raise RuntimeError(
                f"{scenario}: seed set mismatch. Expected {EXPECTED_SEEDS}, found {sorted(found)}"
            )


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    benign_logs = discover_logs(args.benign_root, BENIGN_SCENARIOS)
    attack_logs = discover_logs(args.attack_root, ATTACK_SCENARIOS)
    log_paths = benign_logs + attack_logs

    if not log_paths:
        raise RuntimeError("No logs found.")

    all_rows: list[dict[str, Any]] = []
    integrity_rows: list[dict[str, Any]] = []

    for index, log_path in enumerate(log_paths, start=1):
        print(f"[{index}/{len(log_paths)}] {log_path}")
        rows, integrity = read_run(log_path)
        all_rows.extend(rows)
        integrity_rows.append(integrity)

    records = numericize(pd.DataFrame(all_rows))
    integrity = pd.DataFrame(integrity_rows).sort_values(["scenario", "seed"])
    validate_expected_runs(integrity, args.allow_partial)

    metrics = records[records["kind"].eq("metric")].copy()
    events = records[records["kind"].eq("event")].copy()

    transactions = build_transactions(events)
    node_windows = build_node_windows(metrics)
    transaction_windows = aggregate_transaction_windows(transactions)
    network_windows = build_network_windows(node_windows, transaction_windows)

    # Common time-matched core: same 190–530 s windows in every scenario.
    core = network_windows[
        (network_windows["window_start_s"] >= 190)
        & (network_windows["window_end_s"] <= 530)
    ].copy()

    core_counts = core.groupby("scenario").size().to_dict()
    if not args.allow_partial:
        expected_core = {scenario: 340 for scenario in ALL_SCENARIOS}
        if core_counts != expected_core:
            raise RuntimeError(
                f"Expected 340 core windows per scenario, found {core_counts}"
            )

    all_features = []
    for columns in FEATURE_GROUPS.values():
        all_features.extend(columns)
    all_features = list(dict.fromkeys(all_features))
    missing_features = [column for column in all_features if column not in core.columns]
    if missing_features:
        raise RuntimeError(f"Missing features: {missing_features}")

    feature_matrix_columns = [
        "run_id",
        "scenario",
        "seed",
        "window_start_s",
        "window_end_s",
        "binary_label",
        "cause_family",
        "cause_label",
        "attack_subtype",
        "impairment_level",
        "is_attack",
        "is_impairment",
    ] + all_features

    feature_matrix = core[feature_matrix_columns].copy()

    # Deterministic five-fold seed plan: two unseen seeds per fold.
    seed_to_fold = {
        1001: 1,
        1006: 1,
        1002: 2,
        1007: 2,
        1003: 3,
        1008: 3,
        1004: 4,
        1009: 4,
        1005: 5,
        1010: 5,
    }
    feature_matrix["cv_fold"] = feature_matrix["seed"].map(seed_to_fold)
    core["cv_fold"] = core["seed"].map(seed_to_fold)

    outputs = {
        "integrity": args.output_dir / "AirGuard_integrity_70runs.csv",
        "transactions": args.output_dir / "AirGuard_transactions_120_600s.csv",
        "node_windows": args.output_dir / "AirGuard_node_windows_10s_120_600s.csv",
        "network_windows": args.output_dir / "AirGuard_network_windows_10s_120_600s.csv",
        "core": args.output_dir / "AirGuard_network_core_190_530s.csv",
        "feature_matrix": args.output_dir / "AirGuard_feature_matrix_190_530s.csv",
        "feature_sets": args.output_dir / "feature_sets.json",
        "leakage": args.output_dir / "leakage_columns.txt",
        "manifest": args.output_dir / "dataset_manifest.json",
    }

    integrity.to_csv(outputs["integrity"], index=False)
    transactions.sort_values(
        ["scenario", "seed", "node", "seq"]
    ).to_csv(outputs["transactions"], index=False)
    node_windows.sort_values(
        ["scenario", "seed", "node", "window_end_s"]
    ).to_csv(outputs["node_windows"], index=False)
    network_windows.sort_values(
        ["scenario", "seed", "window_end_s"]
    ).to_csv(outputs["network_windows"], index=False)
    core.sort_values(
        ["scenario", "seed", "window_end_s"]
    ).to_csv(outputs["core"], index=False)
    feature_matrix.sort_values(
        ["scenario", "seed", "window_end_s"]
    ).to_csv(outputs["feature_matrix"], index=False)

    feature_sets = dict(FEATURE_GROUPS)
    feature_sets["all"] = all_features
    outputs["feature_sets"].write_text(
        json.dumps(feature_sets, indent=2), encoding="utf-8"
    )
    outputs["leakage"].write_text(
        "\n".join(sorted(LEAKAGE_COLUMNS)) + "\n", encoding="utf-8"
    )

    manifest = {
        "version": "1.0",
        "run_count": int(integrity["run_id"].nunique()),
        "scenarios": integrity.groupby("scenario")["run_id"].nunique().to_dict(),
        "seeds": sorted(integrity["seed"].astype(int).unique().tolist()),
        "window_s": 10,
        "warmup_excluded_s": [0, 120],
        "full_analysis_s": [120, 600],
        "time_matched_ml_core_s": [190, 530],
        "network_window_rows": len(network_windows),
        "node_window_rows": len(node_windows),
        "core_rows": len(core),
        "core_rows_per_scenario": core_counts,
        "feature_count": len(all_features),
        "features": all_features,
        "cv_policy": "Five fixed folds; test groups are paired seeds and no seed appears in both train and test.",
        "leakage_policy": "Scenario/configuration/attack-instrumentation IDs and time identifiers are excluded.",
        "energest_policy": "Energest is interpreted as radio-activity/load proxy, not joules.",
    }

    output_hashes = {}
    for key, path in outputs.items():
        if key == "manifest":
            continue
        output_hashes[path.name] = sha256_file(path)
    manifest["output_sha256"] = output_hashes
    outputs["manifest"].write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print("\nDataset build complete.")
    print(f"  Runs             : {manifest['run_count']}")
    print(f"  Network windows  : {len(network_windows)}")
    print(f"  Node windows     : {len(node_windows)}")
    print(f"  Core ML rows     : {len(core)}")
    print(f"  Features         : {len(all_features)}")
    print(f"  Output directory : {args.output_dir}")


if __name__ == "__main__":
    main()
