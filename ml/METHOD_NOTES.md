# AirGuard ML yöntem notları

## Neden 190–530 saniye?

Saldırı firmware'inde saldırı 180–540 saniye arasında etkindir. Düğümler farklı global başlangıç ofsetlerine sahip olduğundan, başlangıç ve bitişe komşu pencereler eğitimden çıkarılır. 190–530 saniye, üç saldırı için güvenli aktif çekirdektir.

Clean ve impairment sınıflarında da aynı zaman bölgesinin kullanılması, modelin ağın olgunlaşma zamanını veya simülasyon süresini öğrenmesini engeller.

## Neden seed bazlı CV?

Aynı koşudan gelen ardışık 10 saniyelik pencereler yüksek ölçüde bağımlıdır. Rastgele pencere bölme, aynı koşunun komşu pencerelerini eğitim ve test kümelerine dağıtarak yapay olarak yüksek sonuçlara yol açabilir.

Bu nedenle test fold'ları görülmemiş seed'lerden oluşur:

- Fold 1: 1001, 1006
- Fold 2: 1002, 1007
- Fold 3: 1003, 1008
- Fold 4: 1004, 1009
- Fold 5: 1005, 1010

Her seed bütün senaryolarda bulunduğu için fold'lar sınıf açısından dengelidir.

## Client MAC sayaçları

İstemci MAC sayaçları preferred-parent bağlantısına aittir. Parent değiştiğinde sayaç referansı değişebilir. Bu nedenle parent değişen veya sayaç gerileyen aralıklarda istemci MAC deltaları eksik bırakılır ve median imputation yalnızca eğitim fold'u içinde uygulanır.

## İlk modeller

- Logistic Regression: doğrusal ve yorumlanabilir temel model
- Random Forest: doğrusal olmayan ensemble temel model
- Extra Trees: güçlü ve düşük maliyetli ağaç ensemble modeli

İlk aşamada karmaşık derin öğrenme kullanmadan veri ayrışabilirliği ve sızıntısız performans ölçülür.
