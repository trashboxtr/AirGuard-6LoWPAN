#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

python experiments/analysis/check_analysis_inputs.py

python experiments/analysis/analyze_statistics.py \
  2>&1 | tee experiments/analysis/statistics_console.log

python experiments/analysis/analyze_early_detection.py \
  2>&1 | tee experiments/analysis/early_detection_console.log

python experiments/analysis/analyze_shap.py \
  2>&1 | tee experiments/analysis/shap_console.log

echo
echo "AirGuard analysis stage completed."
echo "Results: experiments/analysis/results"
