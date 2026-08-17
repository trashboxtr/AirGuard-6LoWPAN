# AirGuard out-of-fold SHAP summary

Each fold is explained only on its held-out seeds.
The ranking is based on the mean absolute SHAP attribution.

## attack_subtype

```text
                     feature  mean_abs_shap  sd_abs_shap  folds  explained_samples
           root_mac_rx_delta       0.205736     0.005969      5               1000
      client_mac_acked_delta       0.088460     0.001432      5               1000
client_mac_tx_attempts_delta       0.080564     0.002283      5               1000
         client_mac_rx_delta       0.076112     0.003899      5               1000
        root_mac_acked_delta       0.008050     0.000657      5               1000
  root_mac_tx_attempts_delta       0.007835     0.000949      5               1000
        client_mac_ack_ratio       0.003480     0.000635      5               1000
          root_mac_ack_ratio       0.003445     0.000419      5               1000
           queue_drops_delta       0.000577     0.000257      5               1000
      client_mac_reset_nodes       0.000000     0.000000      5               1000
      client_mac_valid_nodes       0.000000     0.000000      5               1000
```

## binary_attack

```text
                     feature  mean_abs_shap  sd_abs_shap  folds  explained_samples
         client_mac_rx_delta       0.260533     0.007414      5               1000
           root_mac_rx_delta       0.109252     0.002931      5               1000
        client_mac_ack_ratio       0.059729     0.002254      5               1000
      client_mac_acked_delta       0.057906     0.002413      5               1000
          root_mac_ack_ratio       0.044354     0.002566      5               1000
client_mac_tx_attempts_delta       0.035805     0.002595      5               1000
  root_mac_tx_attempts_delta       0.017945     0.000622      5               1000
        root_mac_acked_delta       0.001814     0.000292      5               1000
      client_mac_reset_nodes       0.000637     0.000123      5               1000
      client_mac_valid_nodes       0.000549     0.000101      5               1000
           queue_drops_delta       0.000139     0.000156      5               1000
```

## cause_family

```text
                     feature  mean_abs_shap  sd_abs_shap  folds  explained_samples
                   mean_rank       0.093792     0.001497      5               1000
               mean_etx_x100       0.059881     0.002440      5               1000
         client_mac_rx_delta       0.053414     0.000771      5               1000
client_energest_listen_delta       0.050290     0.002634      5               1000
    client_energest_tx_delta       0.048656     0.002781      5               1000
    client_radio_tx_fraction       0.045813     0.001926      5               1000
          root_mean_etx_x100       0.037340     0.003602      5               1000
                p95_etx_x100       0.027066     0.001537      5               1000
        client_mac_ack_ratio       0.019318     0.003041      5               1000
           root_mac_rx_delta       0.019020     0.001067      5               1000
                std_etx_x100       0.016415     0.002279      5               1000
client_mac_tx_attempts_delta       0.009653     0.001548      5               1000
                   mean_rssi       0.008083     0.009062      5               1000
      client_mac_acked_delta       0.008068     0.000856      5               1000
      root_energest_tx_delta       0.007249     0.000699      5               1000
```

## impairment_severity

```text
             feature  mean_abs_shap  sd_abs_shap  folds  explained_samples
           mean_rank       0.107080     0.006560      5               1000
       mean_etx_x100       0.098578     0.004438      5               1000
  root_mean_etx_x100       0.071907     0.004338      5               1000
        p95_etx_x100       0.043577     0.002372      5               1000
        std_etx_x100       0.027184     0.000969      5               1000
           mean_rssi       0.026675     0.005454      5               1000
parent_changes_delta       0.000852     0.000208      5               1000
      mean_neighbors       0.000000     0.000000      5               1000
      root_mean_rssi       0.000000     0.000000      5               1000
```

## seven_class

```text
                     feature  mean_abs_shap  sd_abs_shap  folds  explained_samples
           root_mac_rx_delta       0.035789     0.001323      5               1000
         client_mac_rx_delta       0.029464     0.000810      5               1000
                   mean_rank       0.028986     0.001925      5               1000
               mean_etx_x100       0.027141     0.001013      5               1000
          root_mean_etx_x100       0.019646     0.001570      5               1000
client_energest_listen_delta       0.017547     0.001121      5               1000
      client_mac_acked_delta       0.017458     0.000255      5               1000
    client_energest_tx_delta       0.017334     0.000376      5               1000
    client_radio_tx_fraction       0.017122     0.000480      5               1000
                p95_etx_x100       0.016434     0.001056      5               1000
client_mac_tx_attempts_delta       0.013575     0.001107      5               1000
        client_mac_ack_ratio       0.010991     0.000495      5               1000
                std_etx_x100       0.009856     0.000603      5               1000
      root_radio_tx_fraction       0.007242     0.000323      5               1000
          root_mac_ack_ratio       0.007134     0.000654      5               1000
```

