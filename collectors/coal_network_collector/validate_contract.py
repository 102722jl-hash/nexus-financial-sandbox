"""Run contract gates and print actionable validation results."""
import json,sqlite3
from pathlib import Path
from manifest import build
ROOT=Path(__file__).parent; db=sqlite3.connect(ROOT/'coal_network.db'); errors=[]; warnings=[]
for table in ['network_registry','network_layers','network_nodes','network_edges','entities','metric_values','formulas','evidence','valuation','review_queue']:
    if not db.execute("select 1 from sqlite_master where type='table' and name=?",(table,)).fetchone(): errors.append('MISSING_TABLE:'+table)
for row in db.execute("select evidence_id from evidence where source_url='' or original_quote='' or page_or_locator='' or published_at='' "): errors.append('INCOMPLETE_EVIDENCE:'+row[0])
for row in db.execute("select edge_id from network_edges where status in ('CONFIRMED','ACTIVE','APPROVED') and (formula_id is null or evidence_id is null or mechanism is null or impact_cap_pct is null)"): errors.append('INVALID_CONFIRMED_EDGE:'+row[0])
fk=db.execute('pragma foreign_key_check').fetchall(); errors.extend('FOREIGN_KEY:'+str(x) for x in fk)
m=build();
if m['counts']['completePaths']==0: warnings.append('COMPLETE_PATH_COUNT_ZERO')
if m['counts']['confirmedEdges']==0: warnings.append('NO_CONFIRMED_EDGES')
report={'errors':errors,'warnings':warnings,'packageStatus':m['packageStatus'],'manifest':'manifest.json'}; (ROOT/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2)); db.close()
