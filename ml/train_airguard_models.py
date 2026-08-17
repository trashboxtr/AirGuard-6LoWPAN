#!/usr/bin/env python3
"""
Leakage-safe baseline experiments for AirGuard-6LoWPAN.

Tasks:
- binary_attack: benign vs attack
- cause_family: normal vs impairment vs attack
- seven_class: seven scenario classes
- attack_subtype: UDP vs DIS vs DIO (attack rows only)
- impairment_severity: Clean vs RX90 vs RX75 vs RX60 (non-attack rows only)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler


TASKS = {
    "binary_attack": {
        "target": "binary_label",
        "filter": None,
    },
    "cause_family": {
        "target": "cause_family",
        "filter": None,
    },
    "seven_class": {
        "target": "cause_label",
        "filter": None,
    },
    "attack_subtype": {
        "target": "attack_subtype",
        "filter": ("binary_label", "attack"),
    },
    "impairment_severity": {
        "target": "cause_label",
        "filter": ("binary_label", "benign"),
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("experiments/ml/processed/AirGuard_feature_matrix_190_530s.csv"),
    )
    parser.add_argument(
        "--feature-sets",
        type=Path,
        default=Path("experiments/ml/processed/feature_sets.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("experiments/ml/results"),
    )
    parser.add_argument(
        "--tasks",
        nargs="+",
        choices=list(TASKS),
        default=["binary_attack", "cause_family", "seven_class", "attack_subtype"],
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=["logistic", "random_forest", "extra_trees"],
        default=["logistic", "random_forest", "extra_trees"],
    )
    parser.add_argument(
        "--feature-set",
        default="all",
        help="Feature set name from feature_sets.json.",
    )
    parser.add_argument(
        "--ablation",
        action="store_true",
        help="Run ExtraTrees for each feature group and the all-feature set.",
    )
    return parser.parse_args()


def make_model(name: str, feature_names: list[str]) -> Pipeline:
    numeric = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler()),
        ]
    )

    if name == "logistic":
        estimator = LogisticRegression(
            max_iter=4000,
            class_weight="balanced",
            solver="lbfgs",
            random_state=42,
        )
        return Pipeline(
            [
                (
                    "preprocess",
                    ColumnTransformer(
                        [("numeric", numeric, feature_names)],
                        remainder="drop",
                    ),
                ),
                ("classifier", estimator),
            ]
        )

    tree_preprocess = ColumnTransformer(
        [
            (
                "numeric",
                SimpleImputer(strategy="median", add_indicator=True),
                feature_names,
            )
        ],
        remainder="drop",
    )

    if name == "random_forest":
        estimator = RandomForestClassifier(
            n_estimators=400,
            max_features="sqrt",
            min_samples_leaf=1,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        )
    elif name == "extra_trees":
        estimator = ExtraTreesClassifier(
            n_estimators=500,
            max_features="sqrt",
            min_samples_leaf=1,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
    else:
        raise ValueError(name)

    return Pipeline(
        [
            ("preprocess", tree_preprocess),
            ("classifier", estimator),
        ]
    )


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    probabilities: np.ndarray | None,
    classes: list[str],
) -> dict[str, float]:
    output = {
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "weighted_f1": f1_score(y_true, y_pred, average="weighted", zero_division=0),
        "macro_precision": precision_score(
            y_true, y_pred, average="macro", zero_division=0
        ),
        "macro_recall": recall_score(
            y_true, y_pred, average="macro", zero_division=0
        ),
        "mcc": matthews_corrcoef(y_true, y_pred),
    }

    if probabilities is None:
        return output

    try:
        if len(classes) == 2:
            positive_index = classes.index("attack") if "attack" in classes else 1
            y_binary = (y_true == positive_index).astype(int)
            output["roc_auc"] = roc_auc_score(
                y_binary, probabilities[:, positive_index]
            )
            output["pr_auc"] = average_precision_score(
                y_binary, probabilities[:, positive_index]
            )
        else:
            output["roc_auc_ovr_macro"] = roc_auc_score(
                y_true,
                probabilities,
                multi_class="ovr",
                average="macro",
                labels=np.arange(len(classes)),
            )
    except ValueError:
        pass

    return output


def model_feature_importance(
    pipeline: Pipeline,
    base_features: list[str],
) -> pd.DataFrame | None:
    classifier = pipeline.named_steps["classifier"]
    if not hasattr(classifier, "feature_importances_"):
        return None

    preprocessor = pipeline.named_steps["preprocess"]
    try:
        transformed_names = preprocessor.get_feature_names_out()
    except Exception:
        transformed_names = np.array(base_features)

    values = classifier.feature_importances_
    if len(transformed_names) != len(values):
        transformed_names = np.array(
            [f"feature_{index}" for index in range(len(values))]
        )

    frame = pd.DataFrame(
        {
            "feature": transformed_names,
            "importance": values,
        }
    ).sort_values("importance", ascending=False)
    return frame


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    data = pd.read_csv(args.data)
    feature_sets = json.loads(args.feature_sets.read_text(encoding="utf-8"))

    requested_sets = [args.feature_set]
    models = list(args.models)
    if args.ablation:
        requested_sets = [
            "application_qos",
            "routing",
            "mac",
            "radio",
            "all",
        ]
        models = ["extra_trees"]

    metric_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    confusion_rows: list[dict[str, Any]] = []
    importance_rows: list[dict[str, Any]] = []

    for task_name in args.tasks:
        task = TASKS[task_name]
        task_data = data.copy()
        if task["filter"]:
            column, value = task["filter"]
            task_data = task_data[task_data[column].eq(value)].copy()

        target = task["target"]
        encoder = LabelEncoder()
        task_data["target_encoded"] = encoder.fit_transform(task_data[target])
        class_names = encoder.classes_.tolist()

        for feature_set_name in requested_sets:
            if feature_set_name not in feature_sets:
                raise KeyError(f"Unknown feature set: {feature_set_name}")

            features = feature_sets[feature_set_name]
            missing = [column for column in features if column not in task_data]
            if missing:
                raise RuntimeError(f"Missing features: {missing}")

            for model_name in models:
                all_true: list[int] = []
                all_pred: list[int] = []
                all_prob: list[np.ndarray] = []

                for fold in range(1, 6):
                    train = task_data[task_data["cv_fold"].ne(fold)].copy()
                    test = task_data[task_data["cv_fold"].eq(fold)].copy()

                    train_seeds = set(train["seed"].astype(int))
                    test_seeds = set(test["seed"].astype(int))
                    overlap = train_seeds & test_seeds
                    if overlap:
                        raise RuntimeError(f"Seed leakage in fold {fold}: {overlap}")

                    pipeline = make_model(model_name, features)
                    pipeline.fit(train[features], train["target_encoded"])

                    prediction = pipeline.predict(test[features])
                    probabilities = (
                        pipeline.predict_proba(test[features])
                        if hasattr(pipeline, "predict_proba")
                        else None
                    )

                    fold_metrics = compute_metrics(
                        test["target_encoded"].to_numpy(),
                        prediction,
                        probabilities,
                        class_names,
                    )
                    metric_rows.append(
                        {
                            "task": task_name,
                            "feature_set": feature_set_name,
                            "model": model_name,
                            "fold": fold,
                            "train_seeds": ",".join(map(str, sorted(train_seeds))),
                            "test_seeds": ",".join(map(str, sorted(test_seeds))),
                            "train_rows": len(train),
                            "test_rows": len(test),
                            **fold_metrics,
                        }
                    )

                    for row_index, (_, original) in enumerate(test.iterrows()):
                        record = {
                            "task": task_name,
                            "feature_set": feature_set_name,
                            "model": model_name,
                            "fold": fold,
                            "run_id": original["run_id"],
                            "scenario": original["scenario"],
                            "seed": int(original["seed"]),
                            "window_start_s": int(original["window_start_s"]),
                            "window_end_s": int(original["window_end_s"]),
                            "y_true": class_names[int(original["target_encoded"])],
                            "y_pred": class_names[int(prediction[row_index])],
                        }
                        if probabilities is not None:
                            for class_index, class_name in enumerate(class_names):
                                record[f"prob_{class_name}"] = probabilities[
                                    row_index, class_index
                                ]
                        prediction_rows.append(record)

                    all_true.extend(test["target_encoded"].astype(int).tolist())
                    all_pred.extend(prediction.astype(int).tolist())
                    if probabilities is not None:
                        all_prob.append(probabilities)

                    model_dir = (
                        args.output_dir
                        / "models"
                        / task_name
                        / feature_set_name
                        / model_name
                    )
                    model_dir.mkdir(parents=True, exist_ok=True)
                    joblib.dump(
                        {
                            "pipeline": pipeline,
                            "classes": class_names,
                            "features": features,
                            "task": task_name,
                            "fold": fold,
                            "test_seeds": sorted(test_seeds),
                        },
                        model_dir / f"fold_{fold}.joblib",
                    )

                    importance = model_feature_importance(pipeline, features)
                    if importance is not None:
                        importance["task"] = task_name
                        importance["feature_set"] = feature_set_name
                        importance["model"] = model_name
                        importance["fold"] = fold
                        importance_rows.extend(importance.to_dict("records"))

                probability_matrix = np.vstack(all_prob) if all_prob else None
                pooled_metrics = compute_metrics(
                    np.asarray(all_true),
                    np.asarray(all_pred),
                    probability_matrix,
                    class_names,
                )
                metric_rows.append(
                    {
                        "task": task_name,
                        "feature_set": feature_set_name,
                        "model": model_name,
                        "fold": "pooled",
                        "train_seeds": "",
                        "test_seeds": "1001-1010",
                        "train_rows": "",
                        "test_rows": len(all_true),
                        **pooled_metrics,
                    }
                )

                matrix = confusion_matrix(
                    all_true,
                    all_pred,
                    labels=np.arange(len(class_names)),
                )
                for true_index, true_name in enumerate(class_names):
                    for pred_index, pred_name in enumerate(class_names):
                        confusion_rows.append(
                            {
                                "task": task_name,
                                "feature_set": feature_set_name,
                                "model": model_name,
                                "true_class": true_name,
                                "predicted_class": pred_name,
                                "count": int(matrix[true_index, pred_index]),
                            }
                        )

                print(
                    f"[OK] {task_name} | {feature_set_name} | {model_name} | "
                    f"macro-F1={pooled_metrics['macro_f1']:.4f}"
                )

    metrics = pd.DataFrame(metric_rows)
    predictions = pd.DataFrame(prediction_rows)
    confusions = pd.DataFrame(confusion_rows)
    importances = pd.DataFrame(importance_rows)

    metrics.to_csv(args.output_dir / "cv_metrics.csv", index=False)
    predictions.to_csv(args.output_dir / "cv_predictions.csv", index=False)
    confusions.to_csv(args.output_dir / "confusion_matrices.csv", index=False)
    if len(importances):
        importances.to_csv(args.output_dir / "feature_importances.csv", index=False)

    pooled = metrics[metrics["fold"].astype(str).eq("pooled")].copy()
    pooled = pooled.sort_values(
        ["task", "macro_f1", "balanced_accuracy"],
        ascending=[True, False, False],
    )
    pooled.to_csv(args.output_dir / "model_ranking.csv", index=False)

    print(f"\nResults: {args.output_dir}")
    print(
        pooled[
            [
                "task",
                "feature_set",
                "model",
                "balanced_accuracy",
                "macro_f1",
                "mcc",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
