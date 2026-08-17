#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd


ROOT = Path.cwd()

REQUIRED_FILES = [
    Path("experiments/ml/processed/AirGuard_feature_matrix_190_530s.csv"),
    Path("experiments/ml/processed/AirGuard_network_windows_10s_120_600s.csv"),
    Path("experiments/ml/processed/feature_sets.json"),
    Path("experiments/ml/results/cv_predictions.csv"),
    Path("experiments/ml/results-ablation/cv_predictions.csv"),
    Path("experiments/ml/results-impairment/cv_predictions.csv"),
    Path("experiments/ml/results-impairment-ablation/cv_predictions.csv"),
]

MODEL_CONFIGS = [
    ("binary_attack", "mac", "extra_trees", Path("experiments/ml/results-ablation")),
    ("cause_family", "all", "random_forest", Path("experiments/ml/results")),
    ("seven_class", "all", "extra_trees", Path("experiments/ml/results")),
    ("attack_subtype", "mac", "extra_trees", Path("experiments/ml/results-ablation")),
    (
        "impairment_severity",
        "routing",
        "extra_trees",
        Path("experiments/ml/results-impairment-ablation"),
    ),
]


def main() -> None:
    errors: list[str] = []

    print("AirGuard analysis input check")
    print("=" * 72)

    for relative in REQUIRED_FILES:
        path = ROOT / relative
        status = "OK" if path.is_file() else "MISSING"
        print(f"[{status:7}] {relative}")
        if not path.is_file():
            errors.append(str(relative))

    if errors:
        raise SystemExit(
            "\nRequired files are missing. Complete the ML stages before analysis."
        )

    feature_matrix_path = ROOT / REQUIRED_FILES[0]
    network_path = ROOT / REQUIRED_FILES[1]
    feature_sets_path = ROOT / REQUIRED_FILES[2]

    feature_matrix = pd.read_csv(feature_matrix_path)
    network = pd.read_csv(network_path)
    feature_sets = json.loads(feature_sets_path.read_text(encoding="utf-8"))

    print("\nDataset checks")
    print("-" * 72)
    print(f"Feature matrix rows : {len(feature_matrix)}")
    print(f"Network window rows : {len(network)}")
    print(f"Scenarios           : {sorted(feature_matrix['scenario'].unique().tolist())}")
    print(f"Seeds               : {sorted(feature_matrix['seed'].astype(int).unique().tolist())}")
    print(f"All-feature count   : {len(feature_sets.get('all', []))}")

    if len(feature_matrix) != 2380:
        errors.append(f"feature matrix row count is {len(feature_matrix)}, expected 2380")
    if len(network) != 3360:
        errors.append(f"network window row count is {len(network)}, expected 3360")
    if len(feature_sets.get("all", [])) != 43:
        errors.append(
            f"all-feature count is {len(feature_sets.get('all', []))}, expected 43"
        )

    print("\nModel checks")
    print("-" * 72)
    for task, feature_set, model, result_dir in MODEL_CONFIGS:
        model_dir = ROOT / result_dir / "models" / task / feature_set / model
        folds = sorted(model_dir.glob("fold_*.joblib"))
        status = "OK" if len(folds) == 5 else "MISSING"
        print(
            f"[{status:7}] {task:22} {feature_set:12} {model:14} "
            f"folds={len(folds)}"
        )
        if len(folds) != 5:
            errors.append(f"{model_dir}: expected 5 fold models")
            continue

        try:
            bundle = joblib.load(folds[0])
            required_keys = {"pipeline", "classes", "features", "task", "fold", "test_seeds"}
            missing_keys = required_keys - set(bundle)
            if missing_keys:
                errors.append(f"{folds[0]} missing keys: {sorted(missing_keys)}")
        except Exception as exc:
            errors.append(f"Could not load {folds[0]}: {exc}")

    if errors:
        print("\nProblems")
        print("-" * 72)
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("\nAll analysis inputs are ready.")


if __name__ == "__main__":
    main()
