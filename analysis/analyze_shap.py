#!/usr/bin/env python3
"""
Out-of-fold SHAP analysis for selected AirGuard task-specific models.

Tree SHAP is computed only on each saved fold's held-out seeds. Global
importance is the mean absolute attribution aggregated over the five test folds.
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
import shap


CONFIGS = [
    {
        "task": "binary_attack",
        "feature_set": "mac",
        "model": "extra_trees",
        "result_dir": Path("experiments/ml/results-ablation"),
        "target": "binary_label",
        "filter": None,
    },
    {
        "task": "cause_family",
        "feature_set": "all",
        "model": "random_forest",
        "result_dir": Path("experiments/ml/results"),
        "target": "cause_family",
        "filter": None,
    },
    {
        "task": "seven_class",
        "feature_set": "all",
        "model": "extra_trees",
        "result_dir": Path("experiments/ml/results"),
        "target": "cause_label",
        "filter": None,
    },
    {
        "task": "attack_subtype",
        "feature_set": "mac",
        "model": "extra_trees",
        "result_dir": Path("experiments/ml/results-ablation"),
        "target": "attack_subtype",
        "filter": ("binary_label", "attack"),
    },
    {
        "task": "impairment_severity",
        "feature_set": "routing",
        "model": "extra_trees",
        "result_dir": Path("experiments/ml/results-impairment-ablation"),
        "target": "cause_label",
        "filter": ("binary_label", "benign"),
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(
            "experiments/ml/processed/"
            "AirGuard_feature_matrix_190_530s.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("experiments/analysis/results/shap"),
    )
    parser.add_argument("--max-samples-per-fold", type=int, default=200)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--top-features", type=int, default=15)
    return parser.parse_args()


def clean_feature_name(name: str) -> str:
    value = str(name)
    if "__" in value:
        value = value.split("__", 1)[1]
    value = value.replace("missingindicator_", "missing__")
    return value


def normalize_shap_values(
    raw_values: Any,
    n_samples: int,
    n_features: int,
) -> np.ndarray:
    if isinstance(raw_values, list):
        arrays = [np.asarray(value) for value in raw_values]
        return np.stack(arrays, axis=2)

    values = np.asarray(raw_values)

    if values.ndim == 2:
        if values.shape != (n_samples, n_features):
            raise RuntimeError(f"Unexpected SHAP shape: {values.shape}")
        return values[:, :, None]

    if values.ndim != 3:
        raise RuntimeError(f"Unexpected SHAP dimensions: {values.shape}")

    if values.shape[0] == n_samples and values.shape[1] == n_features:
        return values
    if values.shape[0] == n_samples and values.shape[2] == n_features:
        return np.transpose(values, (0, 2, 1))
    if values.shape[1] == n_samples and values.shape[2] == n_features:
        return np.transpose(values, (1, 2, 0))

    raise RuntimeError(
        f"Could not align SHAP values {values.shape} "
        f"to samples={n_samples}, features={n_features}"
    )


def sample_test_rows(
    frame: pd.DataFrame,
    target: str,
    max_samples: int,
    random_state: int,
) -> pd.DataFrame:
    if len(frame) <= max_samples:
        return frame.copy()

    groups = []
    classes = sorted(frame[target].astype(str).unique().tolist())
    per_class = max(1, max_samples // len(classes))

    for class_name in classes:
        subset = frame[frame[target].astype(str).eq(class_name)]
        take = min(len(subset), per_class)
        groups.append(
            subset.sample(
                n=take,
                random_state=random_state,
                replace=False,
            )
        )

    sampled = pd.concat(groups, ignore_index=False)
    remaining = max_samples - len(sampled)
    if remaining > 0:
        leftover = frame.drop(index=sampled.index, errors="ignore")
        if len(leftover):
            sampled = pd.concat(
                [
                    sampled,
                    leftover.sample(
                        n=min(remaining, len(leftover)),
                        random_state=random_state + 101,
                        replace=False,
                    ),
                ],
                ignore_index=False,
            )
    return sampled.sort_index()


def class_names_for_values(
    classes: list[str],
    n_outputs: int,
) -> list[str]:
    if n_outputs == len(classes):
        return classes
    if n_outputs == 1 and len(classes) == 2:
        return [classes[1]]
    return [f"output_{index}" for index in range(n_outputs)]


def calculate_configuration(
    data: pd.DataFrame,
    config: dict[str, Any],
    max_samples_per_fold: int,
    random_state: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    task = config["task"]
    feature_set = config["feature_set"]
    model_name = config["model"]
    target = config["target"]

    task_data = data.copy()
    if config["filter"]:
        column, value = config["filter"]
        task_data = task_data[task_data[column].eq(value)].copy()

    model_dir = (
        config["result_dir"]
        / "models"
        / task
        / feature_set
        / model_name
    )

    fold_rows = []
    class_rows = []
    sample_rows = []

    for fold in range(1, 6):
        bundle_path = model_dir / f"fold_{fold}.joblib"
        bundle = joblib.load(bundle_path)

        pipeline = bundle["pipeline"]
        features = list(bundle["features"])
        classes = [str(value) for value in bundle["classes"]]
        test_seeds = [int(value) for value in bundle["test_seeds"]]

        test = task_data[task_data["seed"].isin(test_seeds)].copy()
        test = sample_test_rows(
            test,
            target=target,
            max_samples=max_samples_per_fold,
            random_state=random_state + fold,
        )

        preprocessor = pipeline.named_steps["preprocess"]
        classifier = pipeline.named_steps["classifier"]

        transformed = preprocessor.transform(test[features])
        if hasattr(transformed, "toarray"):
            transformed = transformed.toarray()
        transformed = np.asarray(transformed)

        try:
            transformed_names = [
                clean_feature_name(value)
                for value in preprocessor.get_feature_names_out()
            ]
        except Exception:
            transformed_names = list(features)
            if transformed.shape[1] > len(transformed_names):
                transformed_names.extend(
                    [
                        f"derived_feature_{index}"
                        for index in range(
                            transformed.shape[1] - len(transformed_names)
                        )
                    ]
                )

        explainer = shap.TreeExplainer(classifier)
        raw_values = explainer.shap_values(transformed)
        values = normalize_shap_values(
            raw_values,
            n_samples=transformed.shape[0],
            n_features=transformed.shape[1],
        )
        output_names = class_names_for_values(classes, values.shape[2])

        absolute = np.abs(values)
        fold_global = absolute.mean(axis=(0, 2))
        for feature_name, importance in zip(
            transformed_names,
            fold_global,
        ):
            fold_rows.append(
                {
                    "task": task,
                    "feature_set": feature_set,
                    "model": model_name,
                    "fold": fold,
                    "feature": feature_name,
                    "mean_abs_shap": float(importance),
                    "sample_count": len(test),
                    "test_seeds": ",".join(map(str, test_seeds)),
                }
            )

        for output_index, output_name in enumerate(output_names):
            class_importance = absolute[:, :, output_index].mean(axis=0)
            for feature_name, importance in zip(
                transformed_names,
                class_importance,
            ):
                class_rows.append(
                    {
                        "task": task,
                        "feature_set": feature_set,
                        "model": model_name,
                        "fold": fold,
                        "output_class": output_name,
                        "feature": feature_name,
                        "mean_abs_shap": float(importance),
                        "sample_count": len(test),
                    }
                )

        # Store compact sample-level absolute attributions for auditability.
        sample_absolute = absolute.mean(axis=2)
        for row_position, (_, original) in enumerate(test.iterrows()):
            top_indices = np.argsort(sample_absolute[row_position])[::-1][:5]
            sample_rows.append(
                {
                    "task": task,
                    "feature_set": feature_set,
                    "model": model_name,
                    "fold": fold,
                    "run_id": original["run_id"],
                    "seed": int(original["seed"]),
                    "scenario": original["scenario"],
                    "window_start_s": int(original["window_start_s"]),
                    "window_end_s": int(original["window_end_s"]),
                    "true_target": str(original[target]),
                    "top_features": " | ".join(
                        transformed_names[index] for index in top_indices
                    ),
                    "top_mean_abs_shap": " | ".join(
                        f"{sample_absolute[row_position, index]:.8g}"
                        for index in top_indices
                    ),
                }
            )

        print(
            f"[OK] {task} | fold={fold} | samples={len(test)} | "
            f"features={transformed.shape[1]}"
        )

    return (
        pd.DataFrame(fold_rows),
        pd.DataFrame(class_rows),
        pd.DataFrame(sample_rows),
    )


def aggregate_importance(fold_importance: pd.DataFrame) -> pd.DataFrame:
    return (
        fold_importance.groupby(
            ["task", "feature_set", "model", "feature"],
            as_index=False,
        )
        .agg(
            mean_abs_shap=("mean_abs_shap", "mean"),
            sd_abs_shap=("mean_abs_shap", "std"),
            min_abs_shap=("mean_abs_shap", "min"),
            max_abs_shap=("mean_abs_shap", "max"),
            folds=("fold", "nunique"),
            explained_samples=("sample_count", "sum"),
        )
        .sort_values(
            ["task", "mean_abs_shap"],
            ascending=[True, False],
        )
    )


def aggregate_class_importance(
    class_importance: pd.DataFrame,
) -> pd.DataFrame:
    return (
        class_importance.groupby(
            [
                "task",
                "feature_set",
                "model",
                "output_class",
                "feature",
            ],
            as_index=False,
        )
        .agg(
            mean_abs_shap=("mean_abs_shap", "mean"),
            sd_abs_shap=("mean_abs_shap", "std"),
            folds=("fold", "nunique"),
            explained_samples=("sample_count", "sum"),
        )
        .sort_values(
            ["task", "output_class", "mean_abs_shap"],
            ascending=[True, True, False],
        )
    )


def plot_global(
    global_importance: pd.DataFrame,
    output_dir: Path,
    top_features: int,
) -> None:
    figures = output_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    for task, group in global_importance.groupby("task"):
        top = group.nlargest(top_features, "mean_abs_shap").sort_values(
            "mean_abs_shap"
        )
        fig, ax = plt.subplots(figsize=(9, 6))
        ax.barh(top["feature"], top["mean_abs_shap"])
        ax.set_xlabel("Mean absolute out-of-fold SHAP value")
        ax.set_title(f"{task}: global feature attribution")
        fig.tight_layout()
        fig.savefig(figures / f"{task}_shap_global.png", dpi=220)
        plt.close(fig)


def write_summary(
    global_importance: pd.DataFrame,
    output_path: Path,
    top_features: int,
) -> None:
    lines = [
        "# AirGuard out-of-fold SHAP summary",
        "",
        "Each fold is explained only on its held-out seeds.",
        "The ranking is based on the mean absolute SHAP attribution.",
        "",
    ]

    for task, group in global_importance.groupby("task"):
        lines.extend(
            [
                f"## {task}",
                "",
                "```text",
                group.nlargest(top_features, "mean_abs_shap")[
                    [
                        "feature",
                        "mean_abs_shap",
                        "sd_abs_shap",
                        "folds",
                        "explained_samples",
                    ]
                ].to_string(index=False),
                "```",
                "",
            ]
        )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    data = pd.read_csv(args.data)
    all_fold = []
    all_class = []
    all_samples = []

    for config in CONFIGS:
        fold_frame, class_frame, sample_frame = calculate_configuration(
            data,
            config,
            max_samples_per_fold=args.max_samples_per_fold,
            random_state=args.random_state,
        )
        all_fold.append(fold_frame)
        all_class.append(class_frame)
        all_samples.append(sample_frame)

    fold_importance = pd.concat(all_fold, ignore_index=True)
    class_importance = pd.concat(all_class, ignore_index=True)
    sample_explanations = pd.concat(all_samples, ignore_index=True)

    global_importance = aggregate_importance(fold_importance)
    global_class_importance = aggregate_class_importance(class_importance)

    fold_importance.to_csv(
        args.output_dir / "shap_fold_importance.csv",
        index=False,
    )
    global_importance.to_csv(
        args.output_dir / "shap_global_importance.csv",
        index=False,
    )
    global_class_importance.to_csv(
        args.output_dir / "shap_class_importance.csv",
        index=False,
    )
    sample_explanations.to_csv(
        args.output_dir / "shap_sample_top_features.csv",
        index=False,
    )

    plot_global(
        global_importance,
        args.output_dir,
        top_features=args.top_features,
    )
    write_summary(
        global_importance,
        args.output_dir / "SHAP_SUMMARY.md",
        top_features=args.top_features,
    )

    manifest = {
        "method": "Tree SHAP",
        "evaluation": "out-of-fold by paired seed",
        "max_samples_per_fold": args.max_samples_per_fold,
        "random_state": args.random_state,
        "configurations": [
            {
                key: str(value) if isinstance(value, Path) else value
                for key, value in config.items()
            }
            for config in CONFIGS
        ],
    }
    (args.output_dir / "shap_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print("\nOut-of-fold SHAP analysis complete.")
    print(f"Output: {args.output_dir}")
    print(
        global_importance.groupby("task")
        .head(10)[
            ["task", "feature", "mean_abs_shap", "sd_abs_shap"]
        ]
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
