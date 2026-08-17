# AirGuard seed-clustered statistical summary

The simulation seed is the independent analysis unit.
Individual 10-second windows are not treated as independent replicates.

## Seed-level ranking

```text
               task     feature_set         model  mean_macro_f1  sd_macro_f1  min_macro_f1  max_macro_f1
     attack_subtype             mac   extra_trees       0.995097     0.006933      0.980392      1.000000
     attack_subtype             all   extra_trees       0.994116     0.005064      0.990194      1.000000
     attack_subtype             all random_forest       0.989211     0.009754      0.970582      1.000000
     attack_subtype             all      logistic       0.914558     0.123132      0.652480      1.000000
     attack_subtype           radio   extra_trees       0.723750     0.032606      0.686003      0.792998
     attack_subtype         routing   extra_trees       0.453097     0.103788      0.315588      0.657146
     attack_subtype application_qos   extra_trees       0.433511     0.053387      0.352735      0.507025
      binary_attack             all   extra_trees       1.000000     0.000000      1.000000      1.000000
      binary_attack             all      logistic       1.000000     0.000000      1.000000      1.000000
      binary_attack             mac   extra_trees       1.000000     0.000000      1.000000      1.000000
      binary_attack             all random_forest       0.999142     0.001809      0.995705      1.000000
      binary_attack           radio   extra_trees       0.939995     0.012819      0.914951      0.953179
      binary_attack         routing   extra_trees       0.840028     0.017447      0.814484      0.869080
      binary_attack application_qos   extra_trees       0.635310     0.035289      0.584687      0.687984
       cause_family             all random_forest       0.996686     0.004700      0.986663      1.000000
       cause_family             all      logistic       0.996103     0.004516      0.987176      1.000000
       cause_family             all   extra_trees       0.994704     0.004207      0.986647      1.000000
       cause_family             mac   extra_trees       0.946996     0.025494      0.898922      0.987176
       cause_family           radio   extra_trees       0.860135     0.026316      0.830379      0.892157
       cause_family         routing   extra_trees       0.688823     0.054172      0.609195      0.749501
       cause_family application_qos   extra_trees       0.494029     0.028281      0.452141      0.544477
impairment_severity         routing   extra_trees       0.985150     0.022255      0.932644      1.000000
impairment_severity             all   extra_trees       0.979976     0.021559      0.924845      1.000000
impairment_severity             all random_forest       0.976168     0.025802      0.916944      1.000000
impairment_severity             all      logistic       0.971865     0.024021      0.909814      0.992645
impairment_severity             mac   extra_trees       0.747945     0.032980      0.671521      0.788163
impairment_severity           radio   extra_trees       0.685598     0.053204      0.603417      0.742978
impairment_severity application_qos   extra_trees       0.532478     0.065223      0.468005      0.684332
        seven_class             all   extra_trees       0.985196     0.013856      0.952852      1.000000
        seven_class             all      logistic       0.981328     0.022657      0.931417      1.000000
        seven_class             all random_forest       0.976785     0.022865      0.924320      0.995797
        seven_class             mac   extra_trees       0.857173     0.022631      0.808090      0.887815
        seven_class           radio   extra_trees       0.665976     0.030772      0.622496      0.707680
        seven_class         routing   extra_trees       0.627457     0.036735      0.554890      0.687604
        seven_class application_qos   extra_trees       0.291182     0.038496      0.248433      0.366500
```

## Cluster-bootstrap confidence intervals

```text
               task     feature_set         model  point_estimate  ci_low_95  ci_high_95
     attack_subtype             all   extra_trees        0.994117   0.991176    0.997059
     attack_subtype             all      logistic        0.924116   0.852872    0.978409
     attack_subtype             all random_forest        0.989215   0.983329    0.995098
     attack_subtype application_qos   extra_trees        0.434869   0.404281    0.465016
     attack_subtype             mac   extra_trees        0.995098   0.990196    0.999020
     attack_subtype           radio   extra_trees        0.724481   0.707719    0.745043
     attack_subtype         routing   extra_trees        0.456025   0.397854    0.518947
      binary_attack             all   extra_trees        1.000000   1.000000    1.000000
      binary_attack             all      logistic        1.000000   1.000000    1.000000
      binary_attack             all random_forest        0.999142   0.997856    1.000000
      binary_attack application_qos   extra_trees        0.635913   0.615304    0.656985
      binary_attack             mac   extra_trees        1.000000   1.000000    1.000000
      binary_attack           radio   extra_trees        0.940009   0.932033    0.947223
      binary_attack         routing   extra_trees        0.840362   0.830125    0.850875
       cause_family             all   extra_trees        0.994728   0.992058    0.997375
       cause_family             all      logistic        0.996086   0.993477    0.998693
       cause_family             all random_forest        0.996716   0.994048    0.999346
       cause_family application_qos   extra_trees        0.494887   0.478964    0.512164
       cause_family             mac   extra_trees        0.947191   0.931660    0.961476
       cause_family           radio   extra_trees        0.860270   0.845154    0.875639
       cause_family         routing   extra_trees        0.693054   0.660841    0.721544
impairment_severity             all   extra_trees        0.980200   0.966266    0.990441
impairment_severity             all      logistic        0.972023   0.955611    0.983105
impairment_severity             all random_forest        0.976521   0.960375    0.989705
impairment_severity application_qos   extra_trees        0.534139   0.500980    0.575090
impairment_severity             mac   extra_trees        0.748981   0.727636    0.766488
impairment_severity           radio   extra_trees        0.686171   0.655861    0.715709
impairment_severity         routing   extra_trees        0.985341   0.971460    0.996323
        seven_class             all   extra_trees        0.985324   0.976538    0.992437
        seven_class             all      logistic        0.981502   0.966328    0.992857
        seven_class             all random_forest        0.977282   0.962755    0.988649
        seven_class application_qos   extra_trees        0.292497   0.271102    0.316067
        seven_class             mac   extra_trees        0.857841   0.843939    0.870056
        seven_class           radio   extra_trees        0.666580   0.648606    0.684451
        seven_class         routing   extra_trees        0.629155   0.604765    0.651647
```

## Holm-adjusted selected comparisons

```text
               task                                  config_a                                          config_b  mean_difference_a_minus_b  p_value_raw  p_value_holm  significant_holm_0_05
     attack_subtype          attack_subtype__mac__extra_trees                  attack_subtype__all__extra_trees                   0.000981     0.500000      1.000000                  False
     attack_subtype          attack_subtype__mac__extra_trees                attack_subtype__all__random_forest                   0.005887     0.062500      0.250000                  False
     attack_subtype          attack_subtype__mac__extra_trees                     attack_subtype__all__logistic                   0.080540     0.031250      0.218750                  False
     attack_subtype          attack_subtype__mac__extra_trees                attack_subtype__radio__extra_trees                   0.271347     0.001953      0.041016                   True
     attack_subtype          attack_subtype__mac__extra_trees              attack_subtype__routing__extra_trees                   0.542000     0.001953      0.041016                   True
     attack_subtype          attack_subtype__mac__extra_trees      attack_subtype__application_qos__extra_trees                   0.561586     0.001953      0.041016                   True
     attack_subtype          attack_subtype__all__extra_trees                attack_subtype__all__random_forest                   0.004906     0.250000      0.750000                  False
     attack_subtype          attack_subtype__all__extra_trees                     attack_subtype__all__logistic                   0.079559     0.039062      0.234375                  False
     attack_subtype          attack_subtype__all__extra_trees                attack_subtype__radio__extra_trees                   0.270366     0.001953      0.041016                   True
     attack_subtype          attack_subtype__all__extra_trees              attack_subtype__routing__extra_trees                   0.541019     0.001953      0.041016                   True
     attack_subtype          attack_subtype__all__extra_trees      attack_subtype__application_qos__extra_trees                   0.560605     0.001953      0.041016                   True
     attack_subtype        attack_subtype__all__random_forest                     attack_subtype__all__logistic                   0.074653     0.039062      0.234375                  False
     attack_subtype        attack_subtype__all__random_forest                attack_subtype__radio__extra_trees                   0.265461     0.001953      0.041016                   True
     attack_subtype        attack_subtype__all__random_forest              attack_subtype__routing__extra_trees                   0.536114     0.001953      0.041016                   True
     attack_subtype        attack_subtype__all__random_forest      attack_subtype__application_qos__extra_trees                   0.555700     0.001953      0.041016                   True
     attack_subtype             attack_subtype__all__logistic                attack_subtype__radio__extra_trees                   0.190807     0.005859      0.046875                   True
     attack_subtype             attack_subtype__all__logistic              attack_subtype__routing__extra_trees                   0.461461     0.001953      0.041016                   True
     attack_subtype             attack_subtype__all__logistic      attack_subtype__application_qos__extra_trees                   0.481046     0.001953      0.041016                   True
     attack_subtype        attack_subtype__radio__extra_trees              attack_subtype__routing__extra_trees                   0.270653     0.001953      0.041016                   True
     attack_subtype        attack_subtype__radio__extra_trees      attack_subtype__application_qos__extra_trees                   0.290239     0.001953      0.041016                   True
     attack_subtype      attack_subtype__routing__extra_trees      attack_subtype__application_qos__extra_trees                   0.019586     0.921875      1.000000                  False
      binary_attack           binary_attack__mac__extra_trees                   binary_attack__all__extra_trees                   0.000000     1.000000      1.000000                  False
      binary_attack           binary_attack__mac__extra_trees                 binary_attack__radio__extra_trees                   0.060005     0.001953      0.019531                   True
      binary_attack           binary_attack__mac__extra_trees               binary_attack__routing__extra_trees                   0.159972     0.001953      0.019531                   True
      binary_attack           binary_attack__mac__extra_trees       binary_attack__application_qos__extra_trees                   0.364690     0.001953      0.019531                   True
      binary_attack           binary_attack__all__extra_trees                 binary_attack__radio__extra_trees                   0.060005     0.001953      0.019531                   True
      binary_attack           binary_attack__all__extra_trees               binary_attack__routing__extra_trees                   0.159972     0.001953      0.019531                   True
      binary_attack           binary_attack__all__extra_trees       binary_attack__application_qos__extra_trees                   0.364690     0.001953      0.019531                   True
      binary_attack         binary_attack__radio__extra_trees               binary_attack__routing__extra_trees                   0.099967     0.001953      0.019531                   True
      binary_attack         binary_attack__radio__extra_trees       binary_attack__application_qos__extra_trees                   0.304685     0.001953      0.019531                   True
      binary_attack       binary_attack__routing__extra_trees       binary_attack__application_qos__extra_trees                   0.204717     0.001953      0.019531                   True
       cause_family          cause_family__all__random_forest                    cause_family__all__extra_trees                   0.001982     0.218750      0.218750                  False
       cause_family          cause_family__all__random_forest                    cause_family__mac__extra_trees                   0.049690     0.001953      0.029297                   True
       cause_family          cause_family__all__random_forest                  cause_family__radio__extra_trees                   0.136551     0.001953      0.029297                   True
       cause_family          cause_family__all__random_forest                cause_family__routing__extra_trees                   0.307863     0.001953      0.029297                   True
       cause_family          cause_family__all__random_forest        cause_family__application_qos__extra_trees                   0.502657     0.001953      0.029297                   True
       cause_family            cause_family__all__extra_trees                    cause_family__mac__extra_trees                   0.047708     0.001953      0.029297                   True
       cause_family            cause_family__all__extra_trees                  cause_family__radio__extra_trees                   0.134569     0.001953      0.029297                   True
       cause_family            cause_family__all__extra_trees                cause_family__routing__extra_trees                   0.305881     0.001953      0.029297                   True
       cause_family            cause_family__all__extra_trees        cause_family__application_qos__extra_trees                   0.500675     0.001953      0.029297                   True
       cause_family            cause_family__mac__extra_trees                  cause_family__radio__extra_trees                   0.086860     0.001953      0.029297                   True
       cause_family            cause_family__mac__extra_trees                cause_family__routing__extra_trees                   0.258172     0.001953      0.029297                   True
       cause_family            cause_family__mac__extra_trees        cause_family__application_qos__extra_trees                   0.452967     0.001953      0.029297                   True
       cause_family          cause_family__radio__extra_trees                cause_family__routing__extra_trees                   0.171312     0.001953      0.029297                   True
       cause_family          cause_family__radio__extra_trees        cause_family__application_qos__extra_trees                   0.366106     0.001953      0.029297                   True
       cause_family        cause_family__routing__extra_trees        cause_family__application_qos__extra_trees                   0.194795     0.001953      0.029297                   True
impairment_severity impairment_severity__routing__extra_trees             impairment_severity__all__extra_trees                   0.005175     0.296875      0.890625                  False
impairment_severity impairment_severity__routing__extra_trees           impairment_severity__all__random_forest                   0.008982     0.125000      0.632812                  False
impairment_severity impairment_severity__routing__extra_trees                impairment_severity__all__logistic                   0.013285     0.105469      0.632812                  False
impairment_severity impairment_severity__routing__extra_trees             impairment_severity__mac__extra_trees                   0.237205     0.001953      0.041016                   True
impairment_severity impairment_severity__routing__extra_trees           impairment_severity__radio__extra_trees                   0.299552     0.001953      0.041016                   True
impairment_severity impairment_severity__routing__extra_trees impairment_severity__application_qos__extra_trees                   0.452672     0.001953      0.041016                   True
impairment_severity     impairment_severity__all__extra_trees           impairment_severity__all__random_forest                   0.003808     0.460938      0.921875                  False
impairment_severity     impairment_severity__all__extra_trees                impairment_severity__all__logistic                   0.008110     0.160156      0.640625                  False
impairment_severity     impairment_severity__all__extra_trees             impairment_severity__mac__extra_trees                   0.232031     0.001953      0.041016                   True
impairment_severity     impairment_severity__all__extra_trees           impairment_severity__radio__extra_trees                   0.294378     0.001953      0.041016                   True
impairment_severity     impairment_severity__all__extra_trees impairment_severity__application_qos__extra_trees                   0.447497     0.001953      0.041016                   True
impairment_severity   impairment_severity__all__random_forest                impairment_severity__all__logistic                   0.004303     0.826172      0.921875                  False
impairment_severity   impairment_severity__all__random_forest             impairment_severity__mac__extra_trees                   0.228223     0.001953      0.041016                   True
impairment_severity   impairment_severity__all__random_forest           impairment_severity__radio__extra_trees                   0.290570     0.001953      0.041016                   True
impairment_severity   impairment_severity__all__random_forest impairment_severity__application_qos__extra_trees                   0.443690     0.001953      0.041016                   True
impairment_severity        impairment_severity__all__logistic             impairment_severity__mac__extra_trees                   0.223920     0.001953      0.041016                   True
impairment_severity        impairment_severity__all__logistic           impairment_severity__radio__extra_trees                   0.286267     0.001953      0.041016                   True
impairment_severity        impairment_severity__all__logistic impairment_severity__application_qos__extra_trees                   0.439387     0.001953      0.041016                   True
impairment_severity     impairment_severity__mac__extra_trees           impairment_severity__radio__extra_trees                   0.062347     0.003906      0.041016                   True
impairment_severity     impairment_severity__mac__extra_trees impairment_severity__application_qos__extra_trees                   0.215467     0.001953      0.041016                   True
impairment_severity   impairment_severity__radio__extra_trees impairment_severity__application_qos__extra_trees                   0.153120     0.003906      0.041016                   True
        seven_class             seven_class__all__extra_trees                        seven_class__all__logistic                   0.003869     0.652344      0.750000                  False
        seven_class             seven_class__all__extra_trees                   seven_class__all__random_forest                   0.008411     0.121094      0.363281                  False
        seven_class             seven_class__all__extra_trees                     seven_class__mac__extra_trees                   0.128023     0.001953      0.041016                   True
        seven_class             seven_class__all__extra_trees                   seven_class__radio__extra_trees                   0.319220     0.001953      0.041016                   True
        seven_class             seven_class__all__extra_trees                 seven_class__routing__extra_trees                   0.357739     0.001953      0.041016                   True
        seven_class             seven_class__all__extra_trees         seven_class__application_qos__extra_trees                   0.694015     0.001953      0.041016                   True
        seven_class                seven_class__all__logistic                   seven_class__all__random_forest                   0.004543     0.375000      0.750000                  False
        seven_class                seven_class__all__logistic                     seven_class__mac__extra_trees                   0.124154     0.001953      0.041016                   True
        seven_class                seven_class__all__logistic                   seven_class__radio__extra_trees                   0.315352     0.001953      0.041016                   True
        seven_class                seven_class__all__logistic                 seven_class__routing__extra_trees                   0.353871     0.001953      0.041016                   True
        seven_class                seven_class__all__logistic         seven_class__application_qos__extra_trees                   0.690146     0.001953      0.041016                   True
        seven_class           seven_class__all__random_forest                     seven_class__mac__extra_trees                   0.119612     0.001953      0.041016                   True
        seven_class           seven_class__all__random_forest                   seven_class__radio__extra_trees                   0.310809     0.001953      0.041016                   True
        seven_class           seven_class__all__random_forest                 seven_class__routing__extra_trees                   0.349328     0.001953      0.041016                   True
        seven_class           seven_class__all__random_forest         seven_class__application_qos__extra_trees                   0.685603     0.001953      0.041016                   True
        seven_class             seven_class__mac__extra_trees                   seven_class__radio__extra_trees                   0.191197     0.001953      0.041016                   True
        seven_class             seven_class__mac__extra_trees                 seven_class__routing__extra_trees                   0.229716     0.001953      0.041016                   True
        seven_class             seven_class__mac__extra_trees         seven_class__application_qos__extra_trees                   0.565992     0.001953      0.041016                   True
        seven_class           seven_class__radio__extra_trees                 seven_class__routing__extra_trees                   0.038519     0.019531      0.078125                  False
        seven_class           seven_class__radio__extra_trees         seven_class__application_qos__extra_trees                   0.374794     0.001953      0.041016                   True
        seven_class         seven_class__routing__extra_trees         seven_class__application_qos__extra_trees                   0.336275     0.001953      0.041016                   True
```
