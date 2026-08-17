#!/usr/bin/env python3
"""
Seed-clustered uncertainty and paired statistical comparison for AirGuard.

The unit of resampling/comparison is the simulation seed, not an individual
10-second window. This avoids treating temporally correlated windows from the
same run as independent replicates.
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import friedmanchisquare, wilcoxon
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    matthews_corrcoef,
)


DEFAULT_RESULT_DIRS = [
    Path("experiments/ml/results"),
    Path("experiments/ml/results-ablation"),
    Path("experiments/ml/results-impairment"),
    Path("experiments/ml/results-impairment-ablation"),
]

SELECTED_CONFIGS = {
    "binary_attack": [
        ("mac", "extra_trees"),
        ("all", "extra_trees"),
        ("radio", "extra_trees"),
        ("routing", "extra_trees"),
        ("application_qos", "extra_trees"),
    ],
    "cause_family": [
        ("all", "random_forest"),
        ("all", "extra_trees"),
        ("mac", "extra_trees"),
        ("radio", "extra_trees"),
        ("routing", "extra_trees"),
        ("application_qos", "extra_trees"),
    ],
    "seven_class": [
        ("all", "extra_trees"),
        ("all", "logistic"),
        ("all", "random_forest"),
        ("mac", "extra_trees"),
        ("radio", "extra_trees"),
        ("routing", "extra_trees"),
        ("application_qos", "extra_trees"),
    ],
    "attack_subtype": [
        ("mac", "extra_trees"),
        ("all", "extra_trees"),
        ("all", "random_forest"),
        ("all", "logistic"),
        ("radio", "extra_trees"),
        ("routing", "extra_trees"),
        ("application_qos", "extra_trees"),
    ],
    "impairment_severity": [
        ("routing", "extra_trees"),
        ("all", "extra_trees"),
        ("all", "random_forest"),
        ("all", "logistic"),
        ("mac", "extra_trees"),
        ("radio", "extra_trees"),
        ("application_qos", "extra_trees"),
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--result-dirs",
        nargs="+",
        type=Path,
        default=DEFAULT_RESULT_DIRS,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("experiments/analysis/results/statistics"),
    )
    parser.add_argument("--bootstrap-iterations", type=int, default=5000)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def configuration_id(task: str, feature_set: str, model: str) -> str:
    return f"{task}__{feature_set}__{model}"


def load_predictions(result_dirs: list[Path]) -> pd.DataFrame:
    frames = []
    priority = 0

    for result_dir in result_dirs:
        path = result_dir / "cv_predictions.csv"
        if not path.is_file():
            print(f"[SKIP] Missing: {path}")
            priority += 1
            continue

        frame = pd.read_csv(path)
        frame["source_dir"] = str(result_dir)
        frame["source_priority"] = priority
        frames.append(frame)
        priority += 1

    if not frames:
        raise RuntimeError("No cv_predictions.csv files found.")

    data = pd.concat(frames, ignore_index=True)
    data["seed"] = data["seed"].astype(int)

    # The same configuration may appear in the main and ablation directories.
    # Keep the first complete source according to user-supplied directory order.
    selected_frames = []
    for key, group in data.groupby(["task", "feature_set", "model"], sort=False):
        source_priority = group["source_priority"].min()
        chosen = group[group["source_priority"].eq(source_priority)].copy()
        selected_frames.append(chosen)

    output = pd.concat(selected_frames, ignore_index=True)
    duplicate_key = [
        "task",
        "feature_set",
        "model",
        "run_id",
        "window_start_s",
        "window_end_s",
    ]
    output = output.drop_duplicates(duplicate_key, keep="first")
    return output


def metric_dict(y_true: pd.Series, y_pred: pd.Series) -> dict[str, float]:
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "weighted_f1": f1_score(
            y_true, y_pred, average="weighted", zero_division=0
        ),
        "mcc": matthews_corrcoef(y_true, y_pred),
    }


def build_seed_metrics(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = ["task", "feature_set", "model", "seed"]

    for keys, group in data.groupby(group_columns):
        task, feature_set, model, seed = keys
        rows.append(
            {
                "task": task,
                "feature_set": feature_set,
                "model": model,
                "configuration": configuration_id(task, feature_set, model),
                "seed": int(seed),
                "rows": len(group),
                **metric_dict(group["y_true"], group["y_pred"]),
            }
        )
    return pd.DataFrame(rows)


def percentile_interval(values: list[float]) -> tuple[float, float]:
    return (
        float(np.percentile(values, 2.5)),
        float(np.percentile(values, 97.5)),
    )


def cluster_bootstrap(
    data: pd.DataFrame,
    iterations: int,
    random_state: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(random_state)
    rows: list[dict[str, Any]] = []

    for keys, group in data.groupby(["task", "feature_set", "model"]):
        task, feature_set, model = keys
        seeds = sorted(group["seed"].astype(int).unique().tolist())

        point = metric_dict(group["y_true"], group["y_pred"])
        distributions = {name: [] for name in point}

        seed_groups = {
            seed: group[group["seed"].eq(seed)].copy()
            for seed in seeds
        }

        for _ in range(iterations):
            sampled_seeds = rng.choice(seeds, size=len(seeds), replace=True)
            sample = pd.concat(
                [seed_groups[int(seed)] for seed in sampled_seeds],
                ignore_index=True,
            )
            metrics = metric_dict(sample["y_true"], sample["y_pred"])
            for metric_name, value in metrics.items():
                distributions[metric_name].append(value)

        for metric_name, point_value in point.items():
            ci_low, ci_high = percentile_interval(distributions[metric_name])
            rows.append(
                {
                    "task": task,
                    "feature_set": feature_set,
                    "model": model,
                    "configuration": configuration_id(task, feature_set, model),
                    "metric": metric_name,
                    "point_estimate": point_value,
                    "ci_low_95": ci_low,
                    "ci_high_95": ci_high,
                    "bootstrap_iterations": iterations,
                    "cluster_unit": "seed",
                    "seed_count": len(seeds),
                }
            )
    return pd.DataFrame(rows)


def holm_adjust(p_values: list[float]) -> list[float]:
    count = len(p_values)
    if count == 0:
        return []

    order = np.argsort(p_values)
    adjusted = np.empty(count, dtype=float)
    running_max = 0.0

    for rank, index in enumerate(order):
        raw = float(p_values[index])
        candidate = min(1.0, (count - rank) * raw)
        running_max = max(running_max, candidate)
        adjusted[index] = running_max

    return adjusted.tolist()


def selected_seed_table(seed_metrics: pd.DataFrame, task: str) -> pd.DataFrame:
    requested = SELECTED_CONFIGS.get(task, [])
    available = []

    for feature_set, model in requested:
        subset = seed_metrics[
            seed_metrics["task"].eq(task)
            & seed_metrics["feature_set"].eq(feature_set)
            & seed_metrics["model"].eq(model)
        ].copy()
        if len(subset):
            available.append(subset)

    if not available:
        return pd.DataFrame()
    return pd.concat(available, ignore_index=True)


def paired_comparisons(seed_metrics: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    pair_rows: list[dict[str, Any]] = []
    omnibus_rows: list[dict[str, Any]] = []

    for task in sorted(seed_metrics["task"].unique()):
        task_data = selected_seed_table(seed_metrics, task)
        if task_data.empty:
            continue

        configs = (
            task_data[["feature_set", "model", "configuration"]]
            .drop_duplicates()
            .to_dict("records")
        )

        complete_configs = []
        arrays = {}
        for config in configs:
            subset = task_data[
                task_data["configuration"].eq(config["configuration"])
            ].sort_values("seed")
            if subset["seed"].nunique() == 10:
                complete_configs.append(config)
                arrays[config["configuration"]] = subset["macro_f1"].to_numpy()

        if len(complete_configs) >= 3:
            try:
                statistic, p_value = friedmanchisquare(
                    *[
                        arrays[config["configuration"]]
                        for config in complete_configs
                    ]
                )
            except ValueError:
                statistic, p_value = 0.0, 1.0
            omnibus_rows.append(
                {
                    "task": task,
                    "metric": "macro_f1",
                    "test": "Friedman",
                    "configuration_count": len(complete_configs),
                    "seed_count": 10,
                    "statistic": float(statistic),
                    "p_value": float(p_value),
                    "configurations": " | ".join(
                        config["configuration"] for config in complete_configs
                    ),
                }
            )

        task_pair_rows = []
        for config_a, config_b in itertools.combinations(complete_configs, 2):
            values_a = arrays[config_a["configuration"]]
            values_b = arrays[config_b["configuration"]]
            differences = values_a - values_b

            if np.allclose(differences, 0.0):
                statistic, p_value = 0.0, 1.0
            else:
                result = wilcoxon(
                    values_a,
                    values_b,
                    alternative="two-sided",
                    zero_method="wilcox",
                    correction=False,
                    method="auto",
                )
                statistic = float(result.statistic)
                p_value = float(result.pvalue)

            task_pair_rows.append(
                {
                    "task": task,
                    "metric": "macro_f1",
                    "config_a": config_a["configuration"],
                    "config_b": config_b["configuration"],
                    "mean_a": float(np.mean(values_a)),
                    "mean_b": float(np.mean(values_b)),
                    "mean_difference_a_minus_b": float(np.mean(differences)),
                    "median_difference_a_minus_b": float(np.median(differences)),
                    "wins_a": int(np.sum(differences > 0)),
                    "ties": int(np.sum(np.isclose(differences, 0))),
                    "wins_b": int(np.sum(differences < 0)),
                    "wilcoxon_statistic": statistic,
                    "p_value_raw": p_value,
                }
            )

        adjusted = holm_adjust([row["p_value_raw"] for row in task_pair_rows])
        for row, adjusted_p in zip(task_pair_rows, adjusted):
            row["p_value_holm"] = adjusted_p
            row["significant_holm_0_05"] = adjusted_p < 0.05
            pair_rows.append(row)

    return pd.DataFrame(pair_rows), pd.DataFrame(omnibus_rows)


def write_summary(
    seed_metrics: pd.DataFrame,
    bootstrap: pd.DataFrame,
    pairwise: pd.DataFrame,
    output_path: Path,
) -> None:
    best = (
        seed_metrics.groupby(["task", "feature_set", "model"], as_index=False)
        .agg(
            mean_macro_f1=("macro_f1", "mean"),
            sd_macro_f1=("macro_f1", "std"),
            min_macro_f1=("macro_f1", "min"),
            max_macro_f1=("macro_f1", "max"),
        )
        .sort_values(["task", "mean_macro_f1"], ascending=[True, False])
    )

    lines = [
        "# AirGuard seed-clustered statistical summary",
        "",
        "The simulation seed is the independent analysis unit.",
        "Individual 10-second windows are not treated as independent replicates.",
        "",
        "## Seed-level ranking",
        "",
        "```text",
        best.to_string(index=False),
        "```",
        "",
        "## Cluster-bootstrap confidence intervals",
        "",
        "```text",
        bootstrap[
            bootstrap["metric"].eq("macro_f1")
        ][
            [
                "task",
                "feature_set",
                "model",
                "point_estimate",
                "ci_low_95",
                "ci_high_95",
            ]
        ].to_string(index=False),
        "```",
        "",
        "## Holm-adjusted selected comparisons",
        "",
    ]

    if len(pairwise):
        lines.extend(
            [
                "```text",
                pairwise[
                    [
                        "task",
                        "config_a",
                        "config_b",
                        "mean_difference_a_minus_b",
                        "p_value_raw",
                        "p_value_holm",
                        "significant_holm_0_05",
                    ]
                ].to_string(index=False),
                "```",
            ]
        )
    else:
        lines.append("No complete paired comparisons were available.")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    predictions = load_predictions(args.result_dirs)
    seed_metrics = build_seed_metrics(predictions)
    bootstrap = cluster_bootstrap(
        predictions,
        iterations=args.bootstrap_iterations,
        random_state=args.random_state,
    )
    pairwise, omnibus = paired_comparisons(seed_metrics)

    seed_metrics.to_csv(args.output_dir / "seed_level_metrics.csv", index=False)
    bootstrap.to_csv(args.output_dir / "cluster_bootstrap_ci.csv", index=False)
    pairwise.to_csv(args.output_dir / "paired_wilcoxon_holm.csv", index=False)
    omnibus.to_csv(args.output_dir / "friedman_tests.csv", index=False)

    write_summary(
        seed_metrics,
        bootstrap,
        pairwise,
        args.output_dir / "STATISTICAL_SUMMARY.md",
    )

    manifest = {
        "bootstrap_iterations": args.bootstrap_iterations,
        "random_state": args.random_state,
        "cluster_unit": "seed",
        "result_dirs": [str(path) for path in args.result_dirs],
        "prediction_rows": len(predictions),
        "tasks": sorted(predictions["task"].unique().tolist()),
        "seed_count": int(predictions["seed"].nunique()),
    }
    (args.output_dir / "statistics_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print("Seed-clustered statistical analysis complete.")
    print(f"Output: {args.output_dir}")
    print(
        seed_metrics.groupby(["task", "feature_set", "model"])["macro_f1"]
        .agg(["mean", "std", "min", "max"])
        .sort_values(["task", "mean"], ascending=[True, False])
        .to_string()
    )


if __name__ == "__main__":
    main()
