# AirGuard-6LoWPAN

Reproducibility package for **AirGuard-6LoWPAN: A Cause-Aware Cross-Layer Framework for Distinguishing Cyberattacks from Benign Radio Impairments in RPL-Based IoT Networks**.

## Overview

AirGuard-6LoWPAN evaluates whether cyberattacks can be distinguished from benign radio degradation in RPL-based IPv6/6LoWPAN networks using cross-layer telemetry. The final experimental design contains 70 Contiki-NG/Cooja runs: seven scenarios × ten paired seeds.

### Scenarios

- Benign: `Clean`, `RX90`, `RX75`, `RX60`
- Attacks: `UDP_Flood`, `DIS_Flood`, `DIO_Flood`

The RX labels denote controlled simulator receive-success settings used to create progressively degraded benign radio conditions; they should not be interpreted as deterministic packet-loss percentages.

## Final dataset

- 70 runs total
- 10 seeds per scenario (`1001`–`1010`)
- 600 s per run
- 10-s non-overlapping windows
- Full 120–600 s data: 3,360 network windows and 53,760 node windows
- Time-matched ML core 190–530 s: 2,380 network windows
- 43 predictive variables: 17 application/QoS, 9 routing, 11 MAC, 6 radio-activity

See `data/processed/dataset_manifest.json`, `data/metadata/run_manifest_70runs.csv`, and `data/metadata/feature_dictionary.csv`.

## Repository structure

```text
firmware/              Contiki-NG application source
simulations/           Cooja configurations for benign and attack scenarios
automation/            Scripts used to run experiment batches
ml/                    Dataset construction and ML training pipeline
analysis/              Seed-level statistics, early detection and SHAP scripts
data/processed/         Final processed 70-run data
 data/metadata/         Fold, feature and run metadata
results/                Final ML and analysis outputs
figures/publication/    Publication-ready figures
supplementary/          Supplementary feature definition table
docs/                   Experimental protocol and attack design
```

## Software environment

The final experiments used Contiki-NG commit:

```text
0ff13c5c6ffbf64959798fc490666afd0fc93090
```

Install Python dependencies with:

```bash
python3 -m pip install -r requirements.txt
```

## Reproduce the processed dataset

The dataset-construction script expects the final raw benign and attack logs at the paths documented in `ml/README_TR.md`. Raw final logs are intended to be archived separately in Zenodo.

```bash
python3 ml/prepare_combined_dataset.py \
  --benign-root raw-data/mote-logs/cross-layer-v1_1/final-600s \
  --attack-root raw-data/mote-logs/attack-v1_0/attack-final-600s \
  --output-dir data/processed
```

Expected output:

```text
Runs            : 70
Network windows : 3360
Node windows    : 53760
Core ML rows    : 2380
Features        : 43
```

## Reproduce model experiments

The original scripts use project-relative defaults under `experiments/ml`. When running from this release layout, supply explicit paths:

```bash
python3 ml/train_airguard_models.py \
  --data data/processed/AirGuard_feature_matrix_190_530s.csv \
  --feature-sets data/processed/feature_sets.json \
  --tasks binary_attack cause_family seven_class attack_subtype \
  --models logistic random_forest extra_trees \
  --feature-set all \
  --output-dir reproduced-results/all-features
```

Layer-wise ablation:

```bash
python3 ml/train_airguard_models.py \
  --data data/processed/AirGuard_feature_matrix_190_530s.csv \
  --feature-sets data/processed/feature_sets.json \
  --tasks binary_attack cause_family seven_class attack_subtype \
  --ablation \
  --output-dir reproduced-results/ablation
```

Impairment-severity models can be reproduced by changing `--tasks` to `impairment_severity`.

## Seed-separated evaluation

Windows from the same simulation seed are never split across training and test data. The fixed held-out seed pairs are:

1. 1001, 1006
2. 1002, 1007
3. 1003, 1008
4. 1004, 1009
5. 1005, 1010

See `data/metadata/fold_assignments.csv`.

## Leakage control

Configuration identifiers, attack instrumentation fields, time/run identifiers and target labels are excluded from predictive inputs. The exact exclusion list is provided in `data/processed/leakage_columns.txt`.

## Statistical analysis and explainability

The independent statistical unit is the simulation seed. Final outputs include seed-clustered bootstrap confidence intervals, Friedman omnibus tests, Holm-adjusted Wilcoxon comparisons, out-of-fold early-detection analyses, and out-of-fold Tree SHAP summaries.

See `analysis/METHOD_NOTES.md` and `results/analysis/`.

## Raw data

The complete 70-run raw Cooja logs are intentionally not duplicated in the GitHub repository. They should be archived as a versioned Zenodo dataset with a persistent DOI. `data/metadata/run_manifest_70runs.csv` provides the final run inventory and hashes.

## Authors

- Enes Açıkgözoğlu
- Oğuzhan Kilim

## Citation

A final article citation and Zenodo DOI will be added after publication/repository deposition. See `CITATION.cff`.

## License

A repository license should be selected before public release. No license is asserted by this preparation package.
