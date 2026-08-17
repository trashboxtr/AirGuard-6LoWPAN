# AirGuard early-detection summary

Detection time is reported at the end of the 10-second window in which the decision becomes available.
All predictions are out-of-fold: the evaluated seed is absent from the corresponding training fold.

## Binary attack detection

```text
 scenario  runs  detected_runs  median_latency_s  mean_latency_s  p25_latency_s  p75_latency_s  detected_by_10s  detected_by_20s  detected_by_30s  detected_by_60s  mean_active_positive_fraction  pre_attack_false_positive_windows
DIO_Flood    10             10              10.0            11.0           10.0           10.0                9               10               10               10                       0.997222                                  0
DIS_Flood    10             10              10.0            10.0           10.0           10.0               10               10               10               10                       1.000000                                  0
UDP_Flood    10             10              10.0            10.0           10.0           10.0               10               10               10               10                       1.000000                                  0
```

## Attack-subtype identification

```text
 scenario  runs  subtype_detected_runs  median_subtype_latency_s  mean_subtype_latency_s  mean_active_correct_subtype_fraction
DIO_Flood    10                     10                      10.0                    10.0                              0.991667
DIS_Flood    10                     10                      10.0                    10.0                              0.991667
UDP_Flood    10                     10                      10.0                    10.0                              1.000000
```

## Benign false positives

```text
scenario  runs  mean_false_positive_rate  sd_false_positive_rate  total_false_positive_windows  total_windows  mean_max_attack_probability  pooled_false_positive_rate
   Clean    10                       0.0                     0.0                             0            360                       0.1658                         0.0
    RX60    10                       0.0                     0.0                             0            360                       0.0200                         0.0
    RX75    10                       0.0                     0.0                             0            360                       0.0296                         0.0
    RX90    10                       0.0                     0.0                             0            360                       0.1512                         0.0
```
