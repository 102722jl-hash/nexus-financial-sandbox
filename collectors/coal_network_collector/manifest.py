"""Generate the auditable manifest required by the network-pack contract."""
from __future__ import annotations
import hashlib,json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).parent; DB=ROOT/'coal_network.db'; OUT=ROOT/'manifest.json'
TABLES=['network_registry','network_layers','network_nodes','network_edges','entities','metric_values','formulas','evidence','valuation','review_queue','raw_documents']
def count(db,t): return db.execute(f'select count(1) from {t}').fetchone()[0]
def build():
    db=sqlite3.connect(DB)
    nodes={r[0]:r for r in db.execute('select node_id,layer_no,status,editable from network_nodes')}; edges=db.execute('select source_node_id,target_node_id,status from network_edges').fetchall()
    referenced={x for e in edges for x in e[:2]}; isolated=[n for n in nodes if n not in referenced]
    sources=[n for n,r in nodes.items() if r[1] in (1,2,3)]; sinks={n for n,r in nodes.items() if r[1]==6}; adj={}
    for s,t,status in edges: adj.setdefault(s,[]).append(t)
    paths=[]
    def walk(n,path):
        if n in sinks: paths.append(path); return
        if len(path)>12:return
        for x in adj.get(n,[]):
            if x not in path: walk(x,path+[x])
    for n in sources: walk(n,[n])
    edge_confirmed=db.execute("select count(1) from network_edges where status in ('CONFIRMED','ACTIVE','APPROVED')").fetchone()[0]
    editable=sum(r[3] for r in nodes.values());
    manifest={'packageVersion':'2.0-contract-v2','networkId':'coal_power_v1','networkName':'煤炭价格到火电企业盈利传导','networkIntent':'CREATE_NEW_NETWORK','packageStatus':'SIMULATION_READY' if paths and edge_confirmed else 'IMPORT_READY','generatedAt':datetime.now(timezone.utc).isoformat(),'dataCutoff':db.execute("select data_cutoff from network_registry where network_id='coal_power_v1'").fetchone()[0],'tables':{t:{'rows':count(db,t),'status':'PRESENT'} for t in TABLES},'counts':{'nodes':len(nodes),'edges':len(edges),'confirmedEdges':edge_confirmed,'candidateEdges':sum(e[2]=='CANDIDATE' for e in edges),'editableNodes':editable,'isolatedNodes':len(isolated),'completePaths':len(paths)},'validation':{'foreignKeyErrors':len(db.execute('pragma foreign_key_check').fetchall()),'isolatedNodeIds':isolated,'samplePaths':paths[:20]},'reviewStatus':'NEEDS_HUMAN_REVIEW' if edge_confirmed==0 or not paths else 'READY_FOR_REVIEW','formalReady':bool(paths and edge_confirmed)}
    raw=json.dumps(manifest,ensure_ascii=False,indent=2).encode(); OUT.write_bytes(raw); manifest['manifestSha256']=hashlib.sha256(raw).hexdigest(); OUT.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8'); db.close(); return manifest
if __name__=='__main__': print(json.dumps(build(),ensure_ascii=False,indent=2))
