"""Publish SQLite tables into an existing, writer-authorized PostgreSQL schema."""
from __future__ import annotations
import argparse,json,os,sqlite3
from pathlib import Path
import psycopg
from psycopg import sql
ROOT=Path(__file__).parent
TABLES=['network_registry','network_layers','entities','evidence','metric_values','formulas','network_nodes','network_edges','valuation','review_queue','raw_documents']
def pg_type(decl):
    x=(decl or '').upper()
    if 'INT' in x:return 'BIGINT'
    if any(t in x for t in ('REAL','DOUBLE','FLOAT')):return 'DOUBLE PRECISION'
    return 'TEXT'
def meta(db,table):
    info=db.execute(f'pragma table_info({table})').fetchall(); names=[r[1] for r in info]; defs=[]
    for _,name,decl,notnull,default,pk in info:
        item=sql.SQL('{} {}').format(sql.Identifier(name),sql.SQL(pg_type(decl)))
        if notnull:item+=sql.SQL(' NOT NULL')
        defs.append(item)
    pks=[r[1] for r in info if r[5]]
    if pks:defs.append(sql.SQL('PRIMARY KEY ({})').format(sql.SQL(',').join(sql.Identifier(x) for x in pks)))
    return names,defs
def sync(a):
    password=os.environ.get(a.password_env)
    if not password:raise ValueError('missing environment variable: '+a.password_env)
    local=sqlite3.connect(a.sqlite); pg=psycopg.connect(host=a.host,port=a.port,dbname=a.database,user=a.user,password=password,sslmode=a.sslmode,connect_timeout=10)
    try:
        if not pg.execute('select 1 from information_schema.schemata where schema_name=%s',(a.schema,)).fetchone():raise RuntimeError('TARGET_SCHEMA_MISSING: run setup_postgres_roles.py')
        for table in TABLES:
            names,defs=meta(local,table); pg.execute(sql.SQL('create table if not exists {}.{} ({})').format(sql.Identifier(a.schema),sql.Identifier(table),sql.SQL(',').join(defs)))
        for table in reversed(TABLES):pg.execute(sql.SQL('truncate table {}.{}').format(sql.Identifier(a.schema),sql.Identifier(table)))
        counts={}
        for table in TABLES:
            names,_=meta(local,table); rows=local.execute(f'select * from {table}').fetchall(); counts[table]=len(rows)
            if rows:pg.executemany(sql.SQL('insert into {}.{} ({}) values ({})').format(sql.Identifier(a.schema),sql.Identifier(table),sql.SQL(',').join(sql.Identifier(x) for x in names),sql.SQL(',').join(sql.Placeholder() for _ in names)),rows)
        pg.commit(); return {'status':'SYNCED','schema':a.schema,'network_id':a.network_id,'counts':counts}
    except Exception:pg.rollback();raise
    finally:local.close();pg.close()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sqlite',default=str(ROOT/'coal_network.db'));p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=5432);p.add_argument('--database',default='coal_network');p.add_argument('--user',default='coal_network_writer');p.add_argument('--password-env',default='COAL_PG_WRITER_PASSWORD');p.add_argument('--schema',default='coal_network');p.add_argument('--network-id',default='coal_power_v1');p.add_argument('--sslmode',default='prefer');a=p.parse_args();print(json.dumps(sync(a),ensure_ascii=False,indent=2))
