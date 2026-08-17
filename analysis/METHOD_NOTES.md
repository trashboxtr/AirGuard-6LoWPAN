# Scientific method notes

## Statistical unit

The independent unit is the paired simulation seed. Window-level observations
are retained for model fitting and prediction, but confidence intervals and
paired comparisons are clustered or aggregated at seed level.

## Multiple comparisons

Pairwise model and feature-set comparisons use two-sided Wilcoxon signed-rank
tests over the ten paired seed-level Macro-F1 values. Holm correction is
performed separately within each task.

## Early detection

The attack starts at 180 s. A prediction for a 10-second interval becomes
available at its end. With the default two-consecutive-window rule, the earliest
possible sustained detection latency is 20 s. A one-window sensitivity analysis
can report a 10 s minimum latency.

## Explainability

Tree SHAP is computed on each fold's held-out test seeds and then aggregated.
This avoids presenting in-sample explanations as if they represented
generalization behavior.

SHAP attribution magnitude is not interpreted as causality. It quantifies the
selected model's sensitivity to each feature under the evaluated data
distribution.
