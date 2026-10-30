"""Compact validation report for the AI-approved candidate policy."""
import json,sqlite3
from pathlib import Path
from manifest_v2 import build as build_manifest
ROOT=Path(__file__).parent
def validate(db_path=ROOT/'coal_network.db'):
    db=sqlite3.connect(db_path); errors=[]
    for table in ['network_registry','network_layers','network_nodes','network_edges','entities','metric_values','calculated_metric_lineage','metric_definitions','network_edge_templates','formulas','evidence','valuation','review_queue','scenario_runs','scenario_values']:
        if not db.execute("select 1 from sqlite_master where type='table' and name=?",(table,)).fetchone(): errors.append('MISSING_TABLE:'+table)
    incomplete=db.execute("select count(1) from evidence where coalesce(source_url,'')='' or coalesce(original_quote,'')='' or coalesce(page_or_locator,'')='' or coalesce(published_at,'')='' ").fetchone()[0]
    low_tier_facts=db.execute("select count(1) from metric_values m join evidence e on e.evidence_id=m.evidence_id where e.source_tier in ('T3','T4') and m.value_status='SOURCE_FACT'").fetchone()[0]
    fk=list(db.execute('pragma foreign_key_check')); missing_edge_evidence=db.execute("select count(1) from network_edges where status='AI_APPROVED' and evidence_id is null").fetchone()[0]; uncalibrated=db.execute("select count(1) from formulas where status='AI_APPROVED' and parameter_status not in ('AI_CALIBRATED','CALIBRATED_PARAMETER','CALCULATED_LINEAGE')").fetchone()[0]; pending=db.execute("select count(1) from review_queue where review_status='PENDING'").fetchone()[0]
    if incomplete: errors.append(f'INCOMPLETE_EVIDENCE:{incomplete}')
    if low_tier_facts: errors.append(f'LOW_TIER_MARKED_SOURCE_FACT:{low_tier_facts}')
    errors += ['FOREIGN_KEY:'+str(x) for x in fk]; db.close(); manifest=build_manifest(db_path)
    warnings=[]
    if missing_edge_evidence: warnings.append({'code':'AI_CANDIDATE_EDGES_WITHOUT_DIRECT_EVIDENCE','count':missing_edge_evidence})
    if uncalibrated: warnings.append({'code':'FORMULAS_NOT_CALIBRATED','count':uncalibrated})
    if pending: warnings.append({'code':'PENDING_NON_GRAPH_REVIEWS','count':pending})
    if not manifest['formalReady']: warnings.append({'code':'FORMAL_SIMULATION_NOT_READY','count':1})
    report={'errors':errors,'warnings':warnings,'candidateReady':manifest['candidateReady'],'formalReady':manifest['formalReady'],'operationalStatus':'AI_CANDIDATE_READY' if manifest['candidateReady'] and not errors else 'NEEDS_ATTENTION','packageStatus':manifest['packageStatus'],'manifest':'manifest.json'}
    (ROOT/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); return report
if __name__=='__main__':
    report=validate()
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(1 if report['errors'] else 0)
