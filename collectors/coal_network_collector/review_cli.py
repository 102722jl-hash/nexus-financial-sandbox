"""Explicit human-review controls; nothing is promoted implicitly."""
import argparse,json,sqlite3
from pathlib import Path
ROOT=Path(__file__).parent; DB=ROOT/'coal_network.db'; ALLOWED={'NODE':'network_nodes','EDGE':'network_edges','FORMULA':'formulas'}
def list_pending(db,kind=None):
    q='select review_id,object_type,object_id,confidence,reason,required_action from review_queue where review_status="PENDING"'; args=()
    if kind: q+=' and object_type=?'; args=(kind.upper(),)
    return db.execute(q+' order by review_id',args).fetchall()
def approve(db,review_id):
    row=db.execute('select object_type,object_id from review_queue where review_id=? and review_status="PENDING"',(review_id,)).fetchone()
    if not row: raise ValueError('pending review not found')
    kind,obj=row; table=ALLOWED.get(kind)
    if not table: raise ValueError(f'unsupported review type: {kind}')
    field={'NODE':'node_id','EDGE':'edge_id','FORMULA':'formula_id'}[kind]
    db.execute(f"update {table} set status='CONFIRMED' where {field}=?",(obj,))
    if db.execute('select changes()').fetchone()[0]==0: raise ValueError('target object not found')
    db.execute("update review_queue set review_status='APPROVED' where review_id=?",(review_id,)); db.commit()
def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['list','approve']); p.add_argument('--kind',choices=list(ALLOWED)); p.add_argument('--review-id',type=int); p.add_argument('--db',default=str(DB)); a=p.parse_args(); db=sqlite3.connect(a.db)
    if a.command=='list': print(json.dumps([dict(zip(['review_id','object_type','object_id','confidence','reason','required_action'],r)) for r in list_pending(db,a.kind)],ensure_ascii=False,indent=2))
    else:
        if a.review_id is None: p.error('approve requires --review-id')
        approve(db,a.review_id); print(json.dumps({'approved_review_id':a.review_id},ensure_ascii=False))
    db.close()
if __name__=='__main__': main()
