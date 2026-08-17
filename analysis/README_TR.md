# AirGuard XAI, Early Detection and Statistical Analysis v1.0

Bu paket, tamamlanmış AirGuard ML deneylerinin ardından üç bilimsel analizi üretir:

1. Seed-kümeli güven aralıkları ve eşleştirilmiş istatistiksel karşılaştırmalar
2. Out-of-fold erken saldırı tespiti ve saldırı-alt-türü tanımlama
3. Out-of-fold Tree SHAP açıklanabilirlik analizi

## Neden seed analizi?

Aynı simülasyon koşusundaki ardışık 10 saniyelik pencereler bağımsız değildir. Bu nedenle:

- Güven aralıkları seed kümeleri bootstrap edilerek hesaplanır.
- Model/özellik karşılaştırmaları 10 eşleştirilmiş seed üzerindeki Macro-F1 değerleriyle yapılır.
- Çoklu ikili Wilcoxon karşılaştırmalarında Holm düzeltmesi uygulanır.
- Uygun görevlerde Friedman omnibus testi raporlanır.

## Neden out-of-fold SHAP?

Açıklamalar, modelin eğitimde gördüğü pencereler üzerinde değil, her fold'un yalnızca iki görülmemiş test seed'i üzerinde hesaplanır. Böylece açıklanabilirlik sonuçları da çapraz doğrulama protokolüyle uyumlu olur.

Seçilen görev odaklı modeller:

| Görev | Özellik seti | Model |
|---|---|---|
| Binary attack | MAC | Extra Trees |
| Cause family | All cross-layer | Random Forest |
| Seven class | All cross-layer | Extra Trees |
| Attack subtype | MAC | Extra Trees |
| Impairment severity | Routing | Extra Trees |

## Erken tespit tanımı

- Saldırı başlangıcı: 180. saniye
- Pencere uzunluğu: 10 saniye
- Varsayılan karar eşiği: 0.50
- Varsayılan kararlılık kuralı: ardışık iki pozitif pencere
- Karar zamanı: ikinci pozitif pencerenin bitiş zamanı

Örneğin 180–190 ve 190–200 pencereleri pozitifse, sürdürülebilir tespit 200. saniyede kullanılabilir ve gecikme 20 saniyedir.

Binary ve saldırı-alt-türü tahminleri her fold'un yalnızca görülmemiş seed'leri üzerinde çalıştırılır.

## Kurulum

Paketi proje köküne çıkarın:

```bash
cd /home/ubuntu/AirGuard-6LoWPAN
tar -xzf AirGuard_XAI_EarlyDetection_Stats_v1_0.tar.gz
chmod +x experiments/analysis/*.py experiments/analysis/run_all_analysis.sh
```

Sanal ortamı açın:

```bash
source .venv-airguard/bin/activate
```

Gerekli ek paketler:

```bash
python -m pip install -r experiments/analysis/requirements.txt
```

## Ön kontrol

```bash
python experiments/analysis/check_analysis_inputs.py
```

Beklenen ana kontroller:

```text
Feature matrix rows : 2380
Network window rows : 3360
All-feature count   : 43
```

Ayrıca seçilen beş model yapılandırmasının her biri için beş fold modeli bulunmalıdır.

## 1. İstatistiksel analiz

```bash
python experiments/analysis/analyze_statistics.py \
  2>&1 | tee experiments/analysis/statistics_console.log
```

Çıktılar:

```text
experiments/analysis/results/statistics/
├── seed_level_metrics.csv
├── cluster_bootstrap_ci.csv
├── paired_wilcoxon_holm.csv
├── friedman_tests.csv
├── STATISTICAL_SUMMARY.md
└── statistics_manifest.json
```

Bootstrap varsayılan olarak 5.000 seed-kümeli örnekleme yapar. Daha hızlı deneme için:

```bash
python experiments/analysis/analyze_statistics.py \
  --bootstrap-iterations 1000
```

## 2. Erken tespit

```bash
python experiments/analysis/analyze_early_detection.py \
  2>&1 | tee experiments/analysis/early_detection_console.log
```

Çıktılar:

```text
experiments/analysis/results/early-detection/
├── early_detection_window_predictions.csv
├── early_detection_run_summary.csv
├── early_detection_scenario_summary.csv
├── early_subtype_run_summary.csv
├── early_subtype_scenario_summary.csv
├── benign_false_positive_run_summary.csv
├── benign_false_positive_scenario_summary.csv
├── EARLY_DETECTION_SUMMARY.md
├── early_detection_manifest.json
└── figures/
```

Tek pencereyle karar denemesi:

```bash
python experiments/analysis/analyze_early_detection.py \
  --consecutive 1 \
  --output-dir experiments/analysis/results/early-detection-k1
```

Daha katı eşik denemesi:

```bash
python experiments/analysis/analyze_early_detection.py \
  --threshold 0.70 \
  --output-dir experiments/analysis/results/early-detection-th070
```

## 3. SHAP

```bash
python experiments/analysis/analyze_shap.py \
  2>&1 | tee experiments/analysis/shap_console.log
```

Varsayılan olarak her fold'dan en fazla 200 dengeli test örneği açıklanır.

Çıktılar:

```text
experiments/analysis/results/shap/
├── shap_fold_importance.csv
├── shap_global_importance.csv
├── shap_class_importance.csv
├── shap_sample_top_features.csv
├── SHAP_SUMMARY.md
├── shap_manifest.json
└── figures/
```

Daha kapsamlı çalışma:

```bash
python experiments/analysis/analyze_shap.py \
  --max-samples-per-fold 400
```

## Tümünü tek komutla çalıştırma

```bash
bash experiments/analysis/run_all_analysis.sh
```

## Sonuç paketleme

```bash
tar -czf AirGuard_Analysis_Results_v1_0.tar.gz \
  experiments/analysis/results \
  experiments/analysis/*_console.log

sha256sum AirGuard_Analysis_Results_v1_0.tar.gz \
  | tee AirGuard_Analysis_Results_v1_0.sha256
```

## Yorumlama sınırları

- SHAP değerleri model davranışını açıklar; nedensel etki kanıtı değildir.
- Energest değerleri fiziksel joule değil, radyo etkinliği/yükü göstergesi olarak yorumlanır.
- Erken tespit sonuçları kontrollü Cooja topolojisi ve mevcut saldırı oranları kapsamında raporlanmalıdır.
