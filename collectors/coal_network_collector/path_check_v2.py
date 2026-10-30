"""Report AI-candidate paths separately from formally confirmed paths."""
import json,sqlite3
from pathlib import Path
from status_policy_v2 import USABLE_STATUSES,FORMAL_STATUSES,placeholders
ROOT=Path(__file__).parent
def find(db,statuses):
    nodes={r[0]:r for r in db.execute('select node_id,layer_no,node_name_cn from network_nodes')}; edges=db.execute(f"select source_node_id,target_node_id from network_edges where status in ({placeholders(statuses)})",statuses).fetchall(); adj={}; paths=[]; sinks={n for n,r in nodes.items() if r[1]==6}
    for s,t in edges: adj.setdefault(s,[]).append(t)
    def walk(n,path):
        if n in sinks: paths.append(path); return
        if len(path)>12:return
        for x in adj.get(n,[]):
            if x not in path: walk(x,path+[x])
    for n,r in nodes.items():
        if r[1] in (1,2,3): walk(n,[n])
    return edges,paths,nodes
def build(db):
    ce,cp,nodes=find(db,USABLE_STATUSES); fe,fp,_=find(db,FORMAL_STATUSES)
    return {'candidate_edges':len(ce),'candidate_complete_paths':len(cp),'candidate_paths':[[nodes[n][2] for n in p] for p in cp[:20]],'formal_edges':len(fe),'formal_complete_paths':len(fp),'formal_paths':[[nodes[n][2] for n in p] for p in fp[:20]],'candidate_status':'AI_CANDIDATE_READY' if cp else 'IMPORT_READY','formal_status':'SIMULATION_READY' if fp else 'NOT_FORMALLY_READY'}
if __name__=='__main__':
    db=sqlite3.connect(ROOT/'coal_network.db'); print(json.dumps(build(db),ensure_ascii=False,indent=2)); db.close()
