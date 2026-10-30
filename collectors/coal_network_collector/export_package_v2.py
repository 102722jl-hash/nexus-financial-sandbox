"""Export the standard tables and the AI-candidate status policy."""
import json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from manifest_v2 import build as build_manifest
ROOT=Path(__file__).parent; TABLES=['network_registry','network_layers','network_nodes','network_edges','entities','metric_values','calculated_metric_lineage','metric_definitions','network_edge_templates','formulas','evidence','valuation','scenario_runs','scenario_values']
def export(db_path=ROOT/'coal_network.db',out=ROOT/'package_export'):
    out=Path(out); out.mkdir(exist_ok=True); db=sqlite3.connect(db_path); files={}
    for table in TABLES:
        cols=[r[1] for r in db.execute(f'pragma table_info({table})')]; path=out/f'{table}.jsonl'; rows=db.execute(f'select * from {table}').fetchall()
        with path.open('w',encoding='utf-8') as f:
            for row in rows: f.write(json.dumps(dict(zip(cols,row)),ensure_ascii=False)+'\n')
        files[table]={'path':str(path),'rows':len(rows)}
    db.close(); state=build_manifest(db_path); package={'packageVersion':state['packageVersion'],'networkId':'coal_power_v1','exportedAt':datetime.now(timezone.utc).isoformat(),'statusPolicy':state['statusPolicy'],'candidateReady':state['candidateReady'],'formalReady':state['formalReady'],'tables':files}; (out/'manifest.json').write_text(json.dumps(package,ensure_ascii=False,indent=2),encoding='utf-8'); return package
if __name__=='__main__': print(json.dumps(export(),ensure_ascii=False,indent=2))
