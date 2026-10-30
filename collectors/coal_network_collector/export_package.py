"""Export standard network tables as JSONL for the sandbox importer."""
import json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).parent; DB=ROOT/'coal_network.db'; TABLES=['network_registry','network_layers','network_nodes','network_edges','entities','metric_values','formulas','evidence','valuation']
def export(out=None):
    out=Path(out or ROOT/'package_export'); out.mkdir(exist_ok=True); db=sqlite3.connect(DB); files={}
    for table in TABLES:
        cols=[r[1] for r in db.execute(f'pragma table_info({table})')]; path=out/f'{table}.jsonl'
        with path.open('w',encoding='utf-8') as f:
            for row in db.execute(f'select * from {table}'): f.write(json.dumps(dict(zip(cols,row)),ensure_ascii=False)+'\n')
        files[table]={'path':str(path),'rows':db.execute(f'select count(1) from {table}').fetchone()[0]}
    manifest={'packageVersion':'2.0-contract-v2','networkId':'coal_power_v1','exportedAt':datetime.now(timezone.utc).isoformat(),'tables':files}; (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8'); db.close(); return manifest
if __name__=='__main__': print(json.dumps(export(),ensure_ascii=False,indent=2))
