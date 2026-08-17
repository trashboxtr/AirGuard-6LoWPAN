# AirGuard-6LoWPAN Birleşik Veri Seti ve ML Pipeline v1.0

Bu paket, aynı 10 seed ile üretilen şu 70 koşuyu tek ve sızıntısız veri yapısında birleştirir:

- Clean: 10 koşu
- RX90: 10 koşu
- RX75: 10 koşu
- RX60: 10 koşu
- UDP_Flood: 10 koşu
- DIS_Flood: 10 koşu
- DIO_Flood: 10 koşu

## Temel bilimsel kararlar

- İlk 120 saniye warm-up olarak çıkarılır.
- ML karşılaştırması için tüm yedi sınıfta aynı zaman bölgesi kullanılır: 190–530 saniye.
- 10 saniyelik pencereleme uygulanır.
- Her sınıf 10 seed × 34 pencere = 340 örnek üretir.
- Yedi sınıflı çekirdek veri seti toplam 2.380 örnektir.
- Eğitim/test ayrımı pencere bazında rastgele yapılmaz.
- Beş sabit çapraz doğrulama fold'unda her test fold'u iki görülmemiş seed içerir.
- Aynı seed hiçbir fold'da hem eğitim hem test içinde bulunmaz.

## Model girdisine alınmayan alanlar

Aşağıdaki alanlar etiketleme, deney takibi veya doğrudan saldırı yapılandırmasıdır ve özellik olarak kullanılmaz:

- scenario, run_id, seed
- window_start_s, window_end_s
- rx_success
- attack_mode, attack_active, attack_tx, attack_udp_rx
- attack_name, attack_node
- tüm hedef/etiket sütunları

Node ID de ağ düzeyi ML veri setinde bulunmaz.

## Üretilen görevler

1. binary_attack: benign / attack
2. cause_family: normal / impairment / attack
3. seven_class: Clean, RX90, RX75, RX60, UDP_Flood, DIS_Flood, DIO_Flood
4. attack_subtype: UDP_Flood, DIS_Flood, DIO_Flood
5. impairment_severity: Clean, RX90, RX75, RX60

## Kurulum

Paketi proje köküne çıkarın:

```bash
cd /home/ubuntu/AirGuard-6LoWPAN
tar -xzf AirGuard_ML_Pipeline_v1_0.tar.gz
chmod +x experiments/ml/*.py experiments/ml/run_pipeline.sh
```

Gerekli paketler:

```bash
python3 -m pip install -r experiments/ml/requirements.txt
```

Mevcut ortamda NumPy, pandas, scikit-learn ve joblib zaten kuruluysa bu adım gerekli değildir.

## Ön koşullar

Şu iki ham log kökü mevcut olmalıdır:

```text
raw-data/mote-logs/cross-layer-v1_1/final-600s
raw-data/mote-logs/attack-v1_0/attack-final-600s
```

Her senaryoda 10 log ve 10 metadata bulunmalıdır.

## Veri setini hazırla

```bash
cd /home/ubuntu/AirGuard-6LoWPAN

python3 experiments/ml/prepare_combined_dataset.py
```

Beklenen özet:

```text
Runs             : 70
Network windows  : 3360
Node windows     : 53760
Core ML rows     : 2380
```

Çıktılar:

```text
experiments/ml/processed/
├── AirGuard_integrity_70runs.csv
├── AirGuard_transactions_120_600s.csv
├── AirGuard_node_windows_10s_120_600s.csv
├── AirGuard_network_windows_10s_120_600s.csv
├── AirGuard_network_core_190_530s.csv
├── AirGuard_feature_matrix_190_530s.csv
├── feature_sets.json
├── leakage_columns.txt
└── dataset_manifest.json
```

## İlk ML deneylerini çalıştır

```bash
python3 experiments/ml/train_airguard_models.py \
  --tasks binary_attack cause_family seven_class attack_subtype \
  --models logistic random_forest extra_trees \
  --feature-set all
```

Sonuçlar:

```text
experiments/ml/results/
├── cv_metrics.csv
├── cv_predictions.csv
├── confusion_matrices.csv
├── feature_importances.csv
├── model_ranking.csv
└── models/
```

## Tek komutla tamamı

```bash
bash experiments/ml/run_pipeline.sh
```

## Ablation analizi

Aşağıdaki özellik gruplarını Extra Trees ile ayrı ayrı karşılaştırır:

- application_qos
- routing
- mac
- radio
- all

```bash
python3 experiments/ml/train_airguard_models.py \
  --tasks binary_attack cause_family seven_class \
  --ablation
```

Ablation sonuçlarını ayrı klasöre almak için:

```bash
python3 experiments/ml/train_airguard_models.py \
  --tasks binary_attack cause_family seven_class \
  --ablation \
  --output-dir experiments/ml/results-ablation
```

## Energest yorumu

Cooja hedefindeki Energest TX/listen farkları fiziksel joule olarak kullanılmaz. Bunlar radyo etkinliği veya radyo yükü göstergesi olarak yorumlanmalıdır.
