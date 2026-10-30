"""Manifest with explicit AI-candidate and formal-confirmation tracks."""
import hashlib,json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from status_policy_v2 import CANDIDATE_STATUSES,FORMAL_STATUSES,USABLE_STATUSES,placeholders
from project_state_v2 import sync_cutoff
ROOT=Path(__file__).parent; DB=ROOT/'coal_network.db'; OUT=ROOT/'manifest.json'
TABLES=['network_registry','network_layers','network_edges','entities','metric_values','calculated_metric_lineage','metric_definitions','network_edge_templates','formulas','network_nodes','evidence','valuation','review_queue','raw_documents','scenario_runs','scenario_values']
def paths(nodes,edges):
    adj={}; sinks={n for n,r in nodes.items() if r[0]==6}; sources=[n for n,r in nodes.items() if r[0] in (1,2,3)]; found=[]
    for s,t in edges: adj.setdefault(s,[]).append(t)
    def walk(n,path):
        if n in sinks: found.append(path); return
        if len(path)>12:return
        for x in adj.get(n,[]):
            if x not in path: walk(x,path+[x])
    for n in sources: walk(n,[n])
    return found
def build(db_path=DB):
    db=sqlite3.connect(db_path); cutoff=sync_cutoff(db); nodes={r[0]:(r[1],r[2],r[3]) for r in db.execute('select node_id,layer_no,status,editable from network_nodes')}; all_edges=list(db.execute('select source_node_id,target_node_id,status from network_edges'))
    candidate_edges=[e[:2] for e in all_edges if e[2] in USABLE_STATUSES]; formal_edges=[e[:2] for e in all_edges if e[2] in FORMAL_STATUSES]; candidate_paths=paths(nodes,candidate_edges); formal_paths=paths(nodes,formal_edges); referenced={x for e in candidate_edges for x in e}; isolated=[n for n in nodes if n not in referenced]
    candidate_count=sum(e[2] in CANDIDATE_STATUSES for e in all_edges); formal_count=sum(e[2] in FORMAL_STATUSES for e in all_edges); calibrated=db.execute("select count(1) from formulas where parameter_status in ('AI_CALIBRATED','CALIBRATED_PARAMETER')").fetchone()[0]; pending=db.execute("select count(1) from review_queue where review_status='PENDING'").fetchone()[0]; ai_reviews=db.execute("select count(1) from review_queue where review_status='AI_APPROVED'").fetchone()[0]
    candidate_ready=bool(candidate_paths); formal_ready=bool(formal_paths and formal_count and calibrated)
    registry=db.execute("select network_name,network_version from network_registry where network_id='coal_power_v1'").fetchone() or ('煤炭价格到火电企业盈利传导','2.1')
    manifest={'packageVersion':registry[1],'networkId':'coal_power_v1','networkName':registry[0],'networkIntent':'UPDATE_EXISTING_NETWORK','packageStatus':'SIMULATION_READY' if formal_ready else 'IMPORT_READY','generatedAt':datetime.now(timezone.utc).isoformat(),'dataCutoff':cutoff,'statusPolicy':{'AI_APPROVED':'INCLUDED_AS_CANDIDATE','formalStatuses':list(FORMAL_STATUSES),'causalConclusion':'ABSTAIN_UNLESS_IDENTIFIED'},'tables':{t:{'rows':db.execute(f'select count(1) from {t}').fetchone()[0],'status':'PRESENT'} for t in TABLES},'counts':{'nodes':len(nodes),'edges':len(all_edges),'aiCandidateEdges':candidate_count,'formalEdges':formal_count,'calibratedFormulas':calibrated,'editableNodes':sum(r[2] for r in nodes.values()),'isolatedNodes':len(isolated),'candidateCompletePaths':len(candidate_paths),'formalCompletePaths':len(formal_paths),'pendingReviews':pending,'aiApprovedReviews':ai_reviews},'validation':{'foreignKeyErrors':len(db.execute('pragma foreign_key_check').fetchall()),'isolatedNodeIds':isolated,'candidateSamplePaths':candidate_paths[:20],'formalSamplePaths':formal_paths[:20]},'candidateReady':candidate_ready,'formalReady':formal_ready,'reviewStatus':'AI_CANDIDATE_READY' if candidate_ready else 'NEEDS_MORE_CANDIDATE_LINKS'}
    raw=json.dumps(manifest,ensure_ascii=False,indent=2).encode(); manifest['manifestSha256']=hashlib.sha256(raw).hexdigest(); OUT.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8'); db.close(); return manifest
if __name__=='__main__': print(json.dumps(build(),ensure_ascii=False,indent=2))
