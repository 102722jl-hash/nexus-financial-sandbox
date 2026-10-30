"""Authoritative one-command collection and AI-candidate package refresh."""
import argparse,json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from collector import seed
from source_adapters import acquire_all
from nce_public import run as collect_nce
from announcement_discovery_fixed import COMPANIES,discover,download_pending
from import_snapshots import run as import_public
from company_announcements import import_pending
from enrich_financials import run as enrich_financials
from sina_market_fixed import run as collect_market
from share_capital import run as complete_market_cap
from complete_contract import install_evidence_defaults,build_baselines,build_valuation
from build_nodes_v2 import build as build_nodes
from build_edges_v3 import build as build_edges
from ai_judge_v2 import run as ai_review
from project_state_v2 import sync_cutoff
from manifest_v2 import build as build_manifest
from validate_v3 import validate
from export_package_v2 import export
ROOT=Path(__file__).parent; DB=ROOT/'coal_network.db'
def stage(results,name,fn):
    try: results[name]=fn()
    except Exception as exc: results[name]={'status':'ERROR','error':str(exc)}
def main():
    p=argparse.ArgumentParser(); p.add_argument('--offline',action='store_true'); p.add_argument('--skip-market',action='store_true'); p.add_argument('--db',default=str(DB)); a=p.parse_args(); path=Path(a.db)
    db=sqlite3.connect(path); db.execute('pragma foreign_keys=on'); db.executescript((ROOT/'complete_schema.sql').read_text(encoding='utf-8')); seed(db); results={'pipelineVersion':'2.1-ai-candidate-policy','mode':'offline' if a.offline else 'online','startedAt':datetime.now(timezone.utc).isoformat()}
    if not a.offline:
        stage(results,'public_acquisition',lambda:acquire_all(db)); stage(results,'nce_public',lambda:collect_nce(db)); stage(results,'announcement_discovery',lambda:{code:len(discover(db,code)) for code in COMPANIES}); stage(results,'announcement_download',lambda:download_pending(db))
        if not a.skip_market: stage(results,'market_proxy',lambda:collect_market(db))
    stage(results,'public_parse',lambda:import_public(db)); stage(results,'company_parse',lambda:import_pending(db)); stage(results,'financial_enrichment',lambda:enrich_financials(db)); install_evidence_defaults(db); db.execute("update evidence set page_or_locator=coalesce(nullif(page_or_locator,''),locator),anchor_at=coalesce(anchor_at,data_cutoff),declared_role=coalesce(declared_role,case when temporal_role='POST_EVENT_VALIDATION' then 'POST_EVENT_VALIDATION' else 'AS_OF_EVIDENCE' end),review_status=case when acceptance_status='ACCEPTED' then 'ACCEPTED' else review_status end")
    results['contract']={'baseline_nodes_updated':build_baselines(db),'valuation_rows_added':build_valuation(db)}; stage(results,'market_cap',lambda:complete_market_cap(db)); stage(results,'nodes_created',lambda:build_nodes(db)); stage(results,'edges_created',lambda:build_edges(db)); stage(results,'ai_review',lambda:ai_review(db)); results['data_cutoff']=sync_cutoff(db); db.commit(); db.close()
    results['manifest']=build_manifest(path); results['validation']=validate(path); results['export']=export(path); results['finishedAt']=datetime.now(timezone.utc).isoformat(); (ROOT/'auto_collect_report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(results,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
