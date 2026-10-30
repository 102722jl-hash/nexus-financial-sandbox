"""SQLite-to-PostgreSQL publisher with schema creation from SQLite metadata."""
from __future__ import annotations
import argparse,json,os,sqlite3
from pathlib import Path
try:
    import psycopg
    from psycopg import sql
except ImportError: psycopg=None
ROOT=Path(__file__).parent
TABLES=['network_registry','network_layers','entities','evidence','metric_values','formulas','network_nodes','network_edges','valuation','review_queue','raw_documents']
def pg_type(decl):
    x=(decl or '').upper()
    if 'INT' in x: return 'BIGINT'
    if 'REAL' in x or 'DOUBLE' in x or 'FLOAT' in x: return 'DOUBLE PRECISION'
    if 'BOOL' in x: return 'BOOLEAN'
    return 'TEXT'
def connect(a):
    if psycopg is None: raise RuntimeError('请先安装 psycopg[binary]')
    password=os.environ.get(a.password_env) if a.password_env else a.password
    if not password: raise ValueError('需要 --password-env 或本次 --password，密码不会写入文件')
    return psycopg.connect(host=a.host,port=a.port,dbname=a.database,user=a.user,password=password,sslmode=a.sslmode,connect_timeout=10)
def metadata(local,table):
    cols=local.execute(f'pragma table_info({table})').fetchall(); names=[r[1] for r in cols]; defs=[]
    for _,name,decl,notnull,default,pk in cols:
        d=sql.SQL('{} {}').format(sql.Identifier(name),sql.SQL(pg_type(decl)))
        if notnull: d+=sql.SQL(' NOT NULL')
        defs.append(d)
    pks=[r[1] for r in cols if r[5]]
    if pks: defs.append(sql.SQL('PRIMARY KEY ({})').format(sql.SQL(',').join(sql.Identifier(x) for x in pks)))
    return names,defs
def sync(a):
    local=sqlite3.connect(a.sqlite); pg=connect(a)
    try:
        pg.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(sql.Identifier(a.schema)))
        for table in TABLES:
            names,defs=metadata(local,table)
            pg.execute(sql.SQL('CREATE TABLE IF NOT EXISTS {}.{} ({})').format(sql.Identifier(a.schema),sql.Identifier(table),sql.SQL(',').join(defs)))
        for table in reversed(TABLES):
            names,_=metadata(local,table)
            if 'network_id' in names: pg.execute(sql.SQL('DELETE FROM {}.{} WHERE network_id=%s').format(sql.Identifier(a.schema),sql.Identifier(table)),(a.network_id,))
            else: pg.execute(sql.SQL('TRUNCATE TABLE {}.{}').format(sql.Identifier(a.schema),sql.Identifier(table)))
        counts={}
        for table in TABLES:
            names,_=metadata(local,table); rows=local.execute(f'SELECT * FROM {table}'+(' WHERE network_id=?' if 'network_id' in names else ''),((a.network_id,) if 'network_id' in names else ())).fetchall(); counts[table]=len(rows)
            if not rows: continue
            stmt=sql.SQL('INSERT INTO {}.{} ({}) VALUES ({})').format(sql.Identifier(a.schema),sql.Identifier(table),sql.SQL(',').join(sql.Identifier(x) for x in names),sql.SQL(',').join(sql.Placeholder() for _ in names)); pg.executemany(stmt,rows)
        pg.commit(); return {'status':'SYNCED','schema':a.schema,'network_id':a.network_id,'counts':counts}
    except Exception: pg.rollback(); raise
    finally: local.close(); pg.close()
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--sqlite',default=str(ROOT/'coal_network.db')); p.add_argument('--host',default='127.0.0.1'); p.add_argument('--port',type=int,default=5432); p.add_argument('--database',required=True); p.add_argument('--user',required=True); p.add_argument('--password-env'); p.add_argument('--password'); p.add_argument('--schema',default='coal_network'); p.add_argument('--network-id',default='coal_power_v1'); p.add_argument('--sslmode',default='prefer'); a=p.parse_args(); print(json.dumps(sync(a),ensure_ascii=False,indent=2))
