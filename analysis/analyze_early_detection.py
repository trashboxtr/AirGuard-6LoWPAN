#!/usr/bin/env python3
"""
Out-of-fold early attack detection and subtype identification.

The binary gate and attack subtype models are evaluated only on the two test
seeds assigned to each saved cross-validation fold. Detection becomes available
at the end of each 10-second window.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ATTACK_SCENARIOS = ("UDP_Flood", "DIS_Flood", "DIO_Flood")
BENIGN_SCENARIOS = ("Clean", "RX90", "RX75", "RX60")

FOLD_MAP = {
    1: [1001, 1006],
    2: [1002, 1007],
    3: [1003, 1008],
    4: [1004, 1009],
    5: [1005, 1010],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--network-windows",
        type=Path,
        default=Path(
            "experiments/ml/processed/"
            "AirGuard_network_windows_10s_120_600s.csv"
        ),
    )
    parser.add_argument(
        "--binary-model-dir",
        type=Path,
        default=Path(
            "experiments/ml/results-ablation/models/"
            "binary_attack/mac/extra_trees"
        ),
    )
    parser.add_argument(
        "--subtype-model-dir",
        type=Path,
        default=Path(
            "experiments/ml/results-ablation/models/"
            "attack_subtype/mac/extra_trees"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("experiments/analysis/results/early-detection"),
    )
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--consecutive", type=int, default=2)
    return parser.parse_args()


def normalized_label(value: str) -> str:
    return str(value).strip().lower()


def first_sustained_detection(
    frame: pd.DataFrame,
    positive_column: str,
    threshold: float,
    consecutive: int,
    onset_s: int = 180,
) -> dict[str, Any]:
    frame = frame.sort_values("window_start_s").copy()
    frame = frame[
        (frame["window_start_s"] >= onset_s)
        & (frame["window_end_s"] <= 540)
    ].copy()

    flags = frame[positive_column].ge(threshold).to_numpy()
    starts = frame["window_start_s"].astype(int).to_numpy()
    ends = frame["window_end_s"].astype(int).to_numpy()

    for index in range(0, len(frame) - consecutive + 1):
        segment = flags[index : index + consecutive]
        if not segment.all():
            continue

        contiguous = True
        for offset in range(consecutive - 1):
            if starts[index + offset + 1] != ends[index + offset]:
                contiguous = False
                break
        if not contiguous:
            continue

        detection_end = int(ends[index + consecutive - 1])
        return {
            "detected": 1,
            "detection_window_start_s": int(starts[index]),
            "detection_available_s": detection_end,
            "latency_s": detection_end - onset_s,
        }

    return {
        "detected": 0,
        "detection_window_start_s": np.nan,
        "detection_available_s": np.nan,
        "latency_s": np.nan,
    }


def predict_with_fold_models(
    network: pd.DataFrame,
    binary_model_dir: Path,
    subtype_model_dir: Path,
) -> pd.DataFrame:
    outputs = []

    for fold, test_seeds in FOLD_MAP.items():
        fold_data = network[network["seed"].isin(test_seeds)].copy()

        binary_bundle = joblib.load(binary_model_dir / f"fold_{fold}.joblib")
        binary_pipeline = binary_bundle["pipeline"]
        binary_features = binary_bundle["features"]
        binary_classes = [normalized_label(value) for value in binary_bundle["classes"]]

        missing_binary = [column for column in binary_features if column not in fold_data]
        if missing_binary:
            raise RuntimeError(f"Missing binary features: {missing_binary}")

        binary_probabilities = binary_pipeline.predict_proba(
            fold_data[binary_features]
        )
        attack_index = binary_classes.index("attack")
        fold_data["prob_attack"] = binary_probabilities[:, attack_index]
        fold_data["pred_binary"] = np.where(
            fold_data["prob_attack"] >= 0.5,
            "attack",
            "benign",
        )

        subtype_bundle = joblib.load(subtype_model_dir / f"fold_{fold}.joblib")
        subtype_pipeline = subtype_bundle["pipeline"]
        subtype_features = subtype_bundle["features"]
        subtype_classes = [
            normalized_label(value) for value in subtype_bundle["classes"]
        ]

        missing_subtype = [
            column for column in subtype_features if column not in fold_data
        ]
        if missing_subtype:
            raise RuntimeError(f"Missing subtype features: {missing_subtype}")

        subtype_probabilities = subtype_pipeline.predict_proba(
            fold_data[subtype_features]
        )
        subtype_indices = np.argmax(subtype_probabilities, axis=1)
        fold_data["pred_attack_subtype"] = [
            subtype_classes[index] for index in subtype_indices
        ]
        fold_data["prob_predicted_subtype"] = np.max(
            subtype_probabilities,
            axis=1,
        )

        for class_index, class_name in enumerate(subtype_classes):
            fold_data[f"prob_subtype_{class_name}"] = subtype_probabilities[
                :, class_index
            ]

        fold_data["cv_fold"] = fold
        outputs.append(fold_data)

    return pd.concat(outputs, ignore_index=True)


def run_level_summary(
    predictions: pd.DataFrame,
    threshold: float,
    consecutive: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    detection_rows: list[dict[str, Any]] = []
    subtype_rows: list[dict[str, Any]] = []

    for (scenario, seed, run_id), group in predictions[
        predictions["scenario"].isin(ATTACK_SCENARIOS)
    ].groupby(["scenario", "seed", "run_id"]):
        detection = first_sustained_detection(
            group,
            positive_column="prob_attack",
            threshold=threshold,
            consecutive=consecutive,
        )

        pre_attack = group[
            (group["window_start_s"] >= 120)
            & (group["window_end_s"] <= 180)
        ]
        active = group[
            (group["window_start_s"] >= 180)
            & (group["window_end_s"] <= 540)
        ]

        detection_rows.append(
            {
                "scenario": scenario,
                "seed": int(seed),
                "run_id": run_id,
                "threshold": threshold,
                "consecutive_windows": consecutive,
                **detection,
                "pre_attack_false_positive_windows": int(
                    pre_attack["prob_attack"].ge(threshold).sum()
                ),
                "pre_attack_window_count": len(pre_attack),
                "active_positive_window_fraction": float(
                    active["prob_attack"].ge(threshold).mean()
                ),
                "active_mean_attack_probability": float(
                    active["prob_attack"].mean()
                ),
                "detected_by_10s": int(
                    detection["detected"] and detection["latency_s"] <= 10
                ),
                "detected_by_20s": int(
                    detection["detected"] and detection["latency_s"] <= 20
                ),
                "detected_by_30s": int(
                    detection["detected"] and detection["latency_s"] <= 30
                ),
                "detected_by_60s": int(
                    detection["detected"] and detection["latency_s"] <= 60
                ),
            }
        )

        true_subtype = normalized_label(scenario)
        subtype_group = group.copy()
        subtype_group["correct_subtype_probability"] = subtype_group.get(
            f"prob_subtype_{true_subtype}",
            pd.Series(np.nan, index=subtype_group.index),
        )

        subtype_detection = first_sustained_detection(
            subtype_group,
            positive_column="correct_subtype_probability",
            threshold=threshold,
            consecutive=consecutive,
        )
        subtype_rows.append(
            {
                "scenario": scenario,
                "seed": int(seed),
                "run_id": run_id,
                "true_subtype": true_subtype,
                "threshold": threshold,
                "consecutive_windows": consecutive,
                **subtype_detection,
                "active_correct_subtype_fraction": float(
                    (
                        active["pred_attack_subtype"]
                        .map(normalized_label)
                        .eq(true_subtype)
                    ).mean()
                ),
            }
        )

    return pd.DataFrame(detection_rows), pd.DataFrame(subtype_rows)


def benign_false_positive_summary(
    predictions: pd.DataFrame,
    threshold: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    evaluation = predictions[
        predictions["scenario"].isin(BENIGN_SCENARIOS)
        & (predictions["window_start_s"] >= 180)
        & (predictions["window_end_s"] <= 540)
    ].copy()
    evaluation["false_positive"] = evaluation["prob_attack"].ge(threshold).astype(int)

    for (scenario, seed, run_id), group in evaluation.groupby(
        ["scenario", "seed", "run_id"]
    ):
        rows.append(
            {
                "scenario": scenario,
                "seed": int(seed),
                "run_id": run_id,
                "window_count": len(group),
                "false_positive_windows": int(group["false_positive"].sum()),
                "false_positive_rate": float(group["false_positive"].mean()),
                "mean_attack_probability": float(group["prob_attack"].mean()),
                "max_attack_probability": float(group["prob_attack"].max()),
            }
        )

    run_summary = pd.DataFrame(rows)
    scenario_summary = (
        run_summary.groupby("scenario", as_index=False)
        .agg(
            runs=("run_id", "nunique"),
            mean_false_positive_rate=("false_positive_rate", "mean"),
            sd_false_positive_rate=("false_positive_rate", "std"),
            total_false_positive_windows=("false_positive_windows", "sum"),
            total_windows=("window_count", "sum"),
            mean_max_attack_probability=("max_attack_probability", "mean"),
        )
    )
    scenario_summary["pooled_false_positive_rate"] = (
        scenario_summary["total_false_positive_windows"]
        / scenario_summary["total_windows"]
    )
    return run_summary, scenario_summary


def summarize_attack_runs(
    run_summary: pd.DataFrame,
    subtype_summary: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    detection = (
        run_summary.groupby("scenario", as_index=False)
        .agg(
            runs=("run_id", "nunique"),
            detected_runs=("detected", "sum"),
            median_latency_s=("latency_s", "median"),
            mean_latency_s=("latency_s", "mean"),
            p25_latency_s=("latency_s", lambda values: np.nanpercentile(values, 25)),
            p75_latency_s=("latency_s", lambda values: np.nanpercentile(values, 75)),
            detected_by_10s=("detected_by_10s", "sum"),
            detected_by_20s=("detected_by_20s", "sum"),
            detected_by_30s=("detected_by_30s", "sum"),
            detected_by_60s=("detected_by_60s", "sum"),
            mean_active_positive_fraction=("active_positive_window_fraction", "mean"),
            pre_attack_false_positive_windows=(
                "pre_attack_false_positive_windows",
                "sum",
            ),
        )
    )

    subtype = (
        subtype_summary.groupby("scenario", as_index=False)
        .agg(
            runs=("run_id", "nunique"),
            subtype_detected_runs=("detected", "sum"),
            median_subtype_latency_s=("latency_s", "median"),
            mean_subtype_latency_s=("latency_s", "mean"),
            mean_active_correct_subtype_fraction=(
                "active_correct_subtype_fraction",
                "mean",
            ),
        )
    )
    return detection, subtype


def plot_attack_probability(predictions: pd.DataFrame, output_path: Path) -> None:
    active = predictions[
        predictions["scenario"].isin(ATTACK_SCENARIOS)
        & (predictions["window_start_s"] >= 120)
        & (predictions["window_end_s"] <= 600)
    ].copy()

    summary = (
        active.groupby(["scenario", "window_end_s"], as_index=False)
        .agg(
            mean_probability=("prob_attack", "mean"),
            sd_probability=("prob_attack", "std"),
        )
    )

    fig, ax = plt.subplots(figsize=(10, 5.5))
    for scenario, group in summary.groupby("scenario"):
        group = group.sort_values("window_end_s")
        x = group["window_end_s"].to_numpy()
        mean = group["mean_probability"].to_numpy()
        sd = group["sd_probability"].fillna(0).to_numpy()
        ax.plot(x, mean, label=scenario)
        ax.fill_between(x, np.clip(mean - sd, 0, 1), np.clip(mean + sd, 0, 1), alpha=0.15)

    ax.axvline(180, linestyle="--", linewidth=1, label="Attack start")
    ax.axvline(540, linestyle="--", linewidth=1, label="Attack stop")
    ax.set_xlabel("Simulation time (s)")
    ax.set_ylabel("Out-of-fold attack probability")
    ax.set_ylim(-0.02, 1.02)
    ax.set_title("Early attack probability by scenario")
    ax.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def plot_latency(run_summary: pd.DataFrame, output_path: Path) -> None:
    data = [
        run_summary.loc[
            run_summary["scenario"].eq(scenario), "latency_s"
        ].dropna().to_numpy()
        for scenario in ATTACK_SCENARIOS
    ]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.boxplot(data, tick_labels=list(ATTACK_SCENARIOS))
    ax.set_ylabel("Detection latency (s)")
    ax.set_title("Sustained early detection latency")
    fig.tight_layout()
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def write_summary(
    detection_summary: pd.DataFrame,
    subtype_summary: pd.DataFrame,
    benign_summary: pd.DataFrame,
    output_path: Path,
) -> None:
    lines = [
        "# AirGuard early-detection summary",
        "",
        "Detection time is reported at the end of the 10-second window in which the decision becomes available.",
        "All predictions are out-of-fold: the evaluated seed is absent from the corresponding training fold.",
        "",
        "## Binary attack detection",
        "",
        "```text",
        detection_summary.to_string(index=False),
        "```",
        "",
        "## Attack-subtype identification",
        "",
        "```text",
        subtype_summary.to_string(index=False),
        "```",
        "",
        "## Benign false positives",
        "",
        "```text",
        benign_summary.to_string(index=False),
        "```",
    ]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "figures").mkdir(parents=True, exist_ok=True)

    network = pd.read_csv(args.network_windows)
    network["seed"] = network["seed"].astype(int)

    predictions = predict_with_fold_models(
        network,
        args.binary_model_dir,
        args.subtype_model_dir,
    )

    run_summary, subtype_run_summary = run_level_summary(
        predictions,
        threshold=args.threshold,
        consecutive=args.consecutive,
    )
    benign_run, benign_scenario = benign_false_positive_summary(
        predictions,
        threshold=args.threshold,
    )
    detection_scenario, subtype_scenario = summarize_attack_runs(
        run_summary,
        subtype_run_summary,
    )

    predictions.to_csv(
        args.output_dir / "early_detection_window_predictions.csv",
        index=False,
    )
    run_summary.to_csv(
        args.output_dir / "early_detection_run_summary.csv",
        index=False,
    )
    detection_scenario.to_csv(
        args.output_dir / "early_detection_scenario_summary.csv",
        index=False,
    )
    subtype_run_summary.to_csv(
        args.output_dir / "early_subtype_run_summary.csv",
        index=False,
    )
    subtype_scenario.to_csv(
        args.output_dir / "early_subtype_scenario_summary.csv",
        index=False,
    )
    benign_run.to_csv(
        args.output_dir / "benign_false_positive_run_summary.csv",
        index=False,
    )
    benign_scenario.to_csv(
        args.output_dir / "benign_false_positive_scenario_summary.csv",
        index=False,
    )

    plot_attack_probability(
        predictions,
        args.output_dir / "figures" / "attack_probability_over_time.png",
    )
    plot_latency(
        run_summary,
        args.output_dir / "figures" / "detection_latency_boxplot.png",
    )

    write_summary(
        detection_scenario,
        subtype_scenario,
        benign_scenario,
        args.output_dir / "EARLY_DETECTION_SUMMARY.md",
    )

    manifest = {
        "binary_model_dir": str(args.binary_model_dir),
        "subtype_model_dir": str(args.subtype_model_dir),
        "threshold": args.threshold,
        "consecutive_windows": args.consecutive,
        "window_size_s": 10,
        "attack_start_s": 180,
        "attack_stop_s": 540,
        "decision_timestamp": "window_end_s",
        "evaluation": "out-of-fold by paired seed",
    }
    (args.output_dir / "early_detection_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print("Early-detection analysis complete.")
    print("\nBinary detection")
    print(detection_scenario.to_string(index=False))
    print("\nSubtype identification")
    print(subtype_scenario.to_string(index=False))
    print("\nBenign false positives")
    print(benign_scenario.to_string(index=False))
    print(f"\nOutput: {args.output_dir}")


if __name__ == "__main__":
    main()
