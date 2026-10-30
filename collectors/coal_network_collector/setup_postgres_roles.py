"""Create writer/read-only roles without persisting their passwords."""
import argparse,os
try:
    import psycopg
    from psycopg import sql
except ImportError: psycopg=None
def required_env(name):
    value=os.environ.get(name)
    if not value: raise ValueError('missing environment variable: '+name)
    return value
def main():
    p=argparse.ArgumentParser(); p.add_argument('--host',default='127.0.0.1'); p.add_argument('--port',type=int,default=5432); p.add_argument('--database',default='coal_network'); p.add_argument('--admin-user',default='coal_network_admin'); p.add_argument('--admin-password-env',default='COAL_PG_ADMIN_PASSWORD'); p.add_argument('--writer-password-env',default='COAL_PG_WRITER_PASSWORD'); p.add_argument('--readonly-password-env',default='COAL_PG_READONLY_PASSWORD'); p.add_argument('--schema',default='coal_network'); a=p.parse_args()
    if psycopg is None: raise RuntimeError('请先安装 psycopg[binary]')
    conn=psycopg.connect(host=a.host,port=a.port,dbname=a.database,user=a.admin_user,password=required_env(a.admin_password_env),sslmode='prefer',autocommit=True)
    writer=required_env(a.writer_password_env); readonly=required_env(a.readonly_password_env)
    try:
        for role,password in [('coal_network_writer',writer),('coal_network_readonly',readonly)]:
            if not conn.execute('select 1 from pg_roles where rolname=%s',(role,)).fetchone(): conn.execute(sql.SQL('create role {} login password {}').format(sql.Identifier(role),sql.Literal(password)))
            else: conn.execute(sql.SQL('alter role {} password {}').format(sql.Identifier(role),sql.Literal(password)))
        conn.execute(sql.SQL('create schema if not exists {} authorization {}').format(sql.Identifier(a.schema),sql.Identifier('coal_network_admin')))
        conn.execute(sql.SQL('grant usage,create on schema {} to {}').format(sql.Identifier(a.schema),sql.Identifier('coal_network_writer')))
        conn.execute(sql.SQL('grant usage on schema {} to {}').format(sql.Identifier(a.schema),sql.Identifier('coal_network_readonly')))
        conn.execute(sql.SQL('alter default privileges for role {} in schema {} grant select on tables to {}').format(sql.Identifier('coal_network_writer'),sql.Identifier(a.schema),sql.Identifier('coal_network_readonly')))
        conn.execute(sql.SQL('alter role {} set default_transaction_read_only=on').format(sql.Identifier('coal_network_readonly')))
        print('PostgreSQL roles and schema ready')
    finally: conn.close()
if __name__=='__main__': main()
