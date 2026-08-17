#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

python3 experiments/ml/prepare_combined_dataset.py

python3 experiments/ml/train_airguard_models.py \
  --tasks binary_attack cause_family seven_class attack_subtype \
  --models logistic random_forest extra_trees \
  --feature-set all

echo
echo "AirGuard dataset and baseline model pipeline completed."
echo "Processed data: experiments/ml/processed"
echo "Results       : experiments/ml/results"
