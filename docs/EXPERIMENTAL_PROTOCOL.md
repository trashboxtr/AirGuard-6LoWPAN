# Experimental protocol

- Network: 16 motes in Contiki-NG/Cooja.
- Seeds: 1001–1010 for every scenario.
- Scenarios: Clean, RX90, RX75, RX60, UDP_Flood, DIS_Flood, DIO_Flood.
- Duration: 600 s per run.
- Warm-up: 0–120 s.
- Attack timeline: 180–540 s for attack scenarios.
- Primary full-window analysis: 120–600 s using non-overlapping 10-s windows.
- Time-matched ML core: 190–530 s, yielding 34 windows/run and 2,380 rows total.
- Final feature vector: 43 predictive variables: 17 application/QoS, 9 routing, 11 MAC, and 6 radio-activity variables.
- Cross-validation: five fixed seed-separated folds; see `data/metadata/fold_assignments.csv`.
- Leakage control: scenario/configuration/attack instrumentation, seed/run/time identifiers, and labels are excluded from model inputs; see `data/processed/leakage_columns.txt`.
- Energest variables are treated as radio-activity/load proxies, not calibrated energy in joules.
