"""One-command public-source collection and network package refresh."""
from __future__ import annotations
import argparse,json,sqlite3,traceback
from pathlib import Path
from collector import init_db,seed
from source_adapters import acquire_all
from nce_public import run as collect_nce
from announcement_discovery_fixed import COMPANIES,discover,download_pending
from import_snapshots import run as import_public
from company_announcements import import_pending
from enrich_financials import run as enrich_financials
from complete_contract import install_evidence_defaults,build_baselines,build_valuation
from build_nodes import build as build_nodes
from build_edges import build as build_edges
from manifest import build as build_manifest

ROOT=Path(__file__).parent; DB=ROOT/'coal_network.db'
def stage(results,name,fn):
    try: results[name]=fn()
    except Exception as exc: results[name]={'status':'ERROR','error':str(exc)}
def main():
    p=argparse.ArgumentParser(); p.add_argument('--offline',action='store_true',help='只处理已有快照，不联网'); p.add_argument('--db',default=str(DB)); a=p.parse_args()
    db_path=Path(a.db); init_db(db_path); db=sqlite3.connect(db_path); db.execute('PRAGMA foreign_keys=ON'); seed(db); results={'mode':'offline' if a.offline else 'online'}
    if not a.offline:
        stage(results,'public_acquisition',lambda: acquire_all(db)); stage(results,'nce_public',lambda: collect_nce(db));
        stage(results,'announcement_discovery',lambda: {code:len(discover(db,code)) for code in COMPANIES}); stage(results,'announcement_download',lambda: download_pending(db))
    stage(results,'public_parse',lambda: import_public(db)); stage(results,'company_parse',lambda: import_pending(db)); stage(results,'financial_enrichment',lambda: enrich_financials(db))
    install_evidence_defaults(db); db.execute("UPDATE evidence SET page_or_locator=COALESCE(NULLIF(page_or_locator,''),locator),anchor_at=COALESCE(anchor_at,data_cutoff),declared_role=COALESCE(declared_role,CASE WHEN temporal_role='POST_EVENT_VALIDATION' THEN 'POST_EVENT_VALIDATION' ELSE 'AS_OF_EVIDENCE' END),review_status=CASE WHEN acceptance_status='ACCEPTED' THEN 'ACCEPTED' ELSE review_status END"); results['contract']={'baseline_nodes_updated':build_baselines(db),'valuation_rows_added':build_valuation(db)}; db.commit()
    stage(results,'node_candidates',lambda:build_nodes(db)); stage(results,'edge_candidates',lambda:build_edges(db)); db.commit(); db.close()
    results['manifest']=build_manifest(); (ROOT/'auto_collect_report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(results,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
