"""Count only paths using confirmed edges."""
import json,sqlite3
from pathlib import Path
db=sqlite3.connect(Path(__file__).parent/'coal_network.db'); nodes={r[0]:r for r in db.execute('select node_id,layer_no,node_name_cn from network_nodes')}; edges=db.execute("select source_node_id,target_node_id from network_edges where status in ('CONFIRMED','ACTIVE','APPROVED')").fetchall(); adj={}
for s,t in edges: adj.setdefault(s,[]).append(t)
sources=[n for n,r in nodes.items() if r[1] in (1,2,3)]; sinks={n for n,r in nodes.items() if r[1]==6}; paths=[]
def walk(n,path):
    if n in sinks: paths.append(path); return
    if len(path)>12:return
    for x in adj.get(n,[]):
        if x not in path: walk(x,path+[x])
for n in sources: walk(n,[n])
print(json.dumps({'confirmed_edges':len(edges),'complete_paths':len(paths),'paths':paths[:20],'status':'SIMULATION_READY' if paths else 'IMPORT_READY'},ensure_ascii=False,indent=2)); db.close()
