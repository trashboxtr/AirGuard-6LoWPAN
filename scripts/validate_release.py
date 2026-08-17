#!/usr/bin/env python3
from pathlib import Path
import json
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'data/processed'
checks=[]
def ck(name, cond, detail=''):
    checks.append((name,bool(cond),detail))
manifest=json.loads((P/'dataset_manifest.json').read_text())
ck('manifest run_count', manifest.get('run_count')==70, str(manifest.get('run_count')))
ck('manifest feature_count', manifest.get('feature_count')==43, str(manifest.get('feature_count')))
expected={
 'AirGuard_network_windows_10s_120_600s.csv':3360,
 'AirGuard_node_windows_10s_120_600s.csv':53760,
 'AirGuard_network_core_190_530s.csv':2380,
 'AirGuard_feature_matrix_190_530s.csv':2380,
 'AirGuard_integrity_70runs.csv':70,
}
for fname,n in expected.items():
    df=pd.read_csv(P/fname)
    ck(f'{fname} rows',len(df)==n,f'{len(df)}')
core=pd.read_csv(P/'AirGuard_feature_matrix_190_530s.csv')
ck('7 scenarios',core['scenario'].nunique()==7,str(core['scenario'].value_counts().to_dict()))
ck('340 rows per scenario',(core['scenario'].value_counts()==340).all(),str(core['scenario'].value_counts().to_dict()))
ck('10 seeds',sorted(core['seed'].unique().tolist())==list(range(1001,1011)),str(sorted(core['seed'].unique().tolist())))
integrity=pd.read_csv(P/'AirGuard_integrity_70runs.csv')
for col in ['metadata_valid','complete_marker','test_ok','sha256_matches_metadata','random_seed_matches']:
    ck(f'integrity {col}',integrity[col].astype(bool).all(),str(integrity[col].value_counts().to_dict()))
ck('boot_count=16',(integrity['boot_count']==16).all(),str(integrity['boot_count'].value_counts().to_dict()))
ck('final_metric_count=16',(integrity['final_metric_count']==16).all(),str(integrity['final_metric_count'].value_counts().to_dict()))
failed=[x for x in checks if not x[1]]
for name,ok,detail in checks:
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")
raise SystemExit(1 if failed else 0)
