"""Coletor de saúde (spec 57 §6.10.5): a cada 5 minutos lê o disco, o Postgres e o MinIO, guarda a amostra em
plataforma.saude_amostras (banco `produtos`, 90 dias) e avisa o Uptime Kuma pelos monitores "push" (um por limite crítico).
O Kuma manda o e-mail. Sem Prometheus, sem porta nova: tudo por `docker exec` local. Roda como root (timer rt-saude).
Limites (§6.10.4) podem ser baixados por variável SAUDE_<SINAL> para forçar o alerta nos testes.
Uso: python3 coletor.py [--sem-push]
"""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
UA = {'User-Agent': 'rt-saude/1'}
KUMA = 'https://uptime.rangeltech.net/api/push/'

LIM = {  # crítico (o aviso amarelo fica para o painel)
    'disco_pct': float(os.environ.get('SAUDE_DISCO_PCT', 92)),
    'pg_conexoes_pct': float(os.environ.get('SAUDE_PG_CONEXOES_PCT', 85)),
    'pg_cache_pct': float(os.environ.get('SAUDE_PG_CACHE_PCT', 93)),
    'pg_tx_longa_s': float(os.environ.get('SAUDE_PG_TX_LONGA_S', 1800)),
    'minio_erros_5xx_pct': float(os.environ.get('SAUDE_MINIO_5XX_PCT', 5)),
    'backup_horas': float(os.environ.get('SAUDE_BACKUP_HORAS', 50)),
}


def sh(*cmd, timeout=60):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip()


def psql(sql, db='postgres'):
    rc, out = sh('docker', 'exec', 'postgres', 'psql', '-U', 'platform_admin', '-d', db, '-Atc', sql)
    if rc:
        raise RuntimeError(f'psql: {out[:200]}')
    return out


def infisical(projeto, pasta, arq='/opt/platform/secrets/infisical-leitura.env'):
    cfg = dict(l.strip().split('=', 1) for l in open(arq, encoding='utf-8') if '=' in l and not l.startswith('#'))
    proj = json.load(open(os.path.join(AQUI, '..', 'infisical', 'infisical_projetos.json')))

    def call(path, body=None, tok=None):
        h = dict(UA, **{'Content-Type': 'application/json'}, **({'Authorization': 'Bearer ' + tok} if tok else {}))
        r = urllib.request.Request(cfg['INFISICAL_URL'] + path, data=json.dumps(body).encode() if body else None, headers=h)
        return json.load(urllib.request.urlopen(r, timeout=30))
    tok = call('/api/v1/auth/universal-auth/login', {'clientId': cfg['INFISICAL_CLIENT_ID'], 'clientSecret': cfg['INFISICAL_CLIENT_SECRET']})['accessToken']
    sec = call(f'/api/v3/secrets/raw?workspaceId={proj[projeto]}&environment=prod&secretPath=/{pasta}', tok=tok)['secrets']
    return {s['secretKey']: s['secretValue'] for s in sec}


# ------------------------------------------------------------------ leituras
def ler_disco():
    t = shutil.disk_usage('/')
    return {'total_gb': round(t.total / 1e9, 1), 'usado_gb': round(t.used / 1e9, 1), 'livre_gb': round(t.free / 1e9, 1),
            'pct': round(100 * t.used / t.total, 1)}


def ler_postgres():
    v = psql("""select version(), extract(epoch from now()-pg_postmaster_start_time())::bigint,
        (select count(*) from pg_stat_activity), (select count(*) from pg_stat_activity where state='active'),
        current_setting('max_connections')::int,
        (select round(100.0*sum(blks_hit)/nullif(sum(blks_hit)+sum(blks_read),0),2) from pg_stat_database),
        (select coalesce(max(extract(epoch from now()-xact_start)),0)::bigint from pg_stat_activity where state<>'idle' and xact_start is not null and backend_type='client backend'),
        (select sum(xact_commit+xact_rollback) from pg_stat_database), (select sum(deadlocks) from pg_stat_database),
        (select sum(tup_returned+tup_fetched) from pg_stat_database), (select sum(tup_inserted+tup_updated+tup_deleted) from pg_stat_database)""").split('|')
    bancos = [dict(zip(('banco', 'bytes'), (l.split('|')[0], int(l.split('|')[1])))) for l in
              psql("select datname, pg_database_size(datname) from pg_database where not datistemplate order by 2 desc").splitlines()]
    return {'versao': v[0].split(' on ')[0], 'no_ar_s': int(v[1]), 'conexoes': int(v[2]), 'ativas': int(v[3]), 'max_conexoes': int(v[4]),
            'conexoes_pct': round(100 * int(v[2]) / int(v[4]), 1), 'cache_pct': float(v[5] or 100), 'tx_mais_longa_s': int(v[6]),
            'transacoes': int(v[7]), 'deadlocks': int(v[8]), 'leituras': int(v[9]), 'escritas': int(v[10]), 'bancos': bancos,
            'total_bytes': sum(b['bytes'] for b in bancos)}


def ler_minio():
    cmd = ('mc alias set local http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; '
           'mc ready local >/dev/null 2>&1 && echo PRONTO; mc admin prometheus metrics local 2>/dev/null; '
           'echo ===DU; mc du --depth 2 local 2>/dev/null')
    rc, out = sh('docker', 'exec', 'minio', 'sh', '-c', cmd, timeout=90)
    met, du = (out.split('===DU') + [''])[:2]
    def soma(nome):
        return sum(float(m.group(1)) for m in re.finditer(rf'^{nome}(?:{{[^}}]*}})? ([0-9.e+]+)$', met, re.M))
    buckets = []
    for l in du.strip().splitlines():
        m = re.match(r'(\S+)\s+(\d+) objects?\s+(\S*)', l.replace('\t', ' '))
        if m and m.group(3):
            buckets.append({'bucket': m.group(3), 'tamanho': m.group(1), 'objetos': int(m.group(2))})
    return {'pronto': 'PRONTO' in met, 'discos_online': soma('minio_cluster_drive_online_total'),
            'requisicoes': soma('minio_s3_requests_total'), 'erros_4xx': soma('minio_s3_requests_4xx_errors_total'),
            'erros_5xx': soma('minio_s3_requests_5xx_errors_total'), 'rx_bytes': soma('minio_s3_traffic_received_bytes'),
            'tx_bytes': soma('minio_s3_traffic_sent_bytes'), 'buckets': buckets}


def ler_backup():
    try:
        j = json.load(open('/opt/platform/data/backups/last_ok.json'))
        fim = dt.datetime.fromisoformat(j['finished_at'])
        return {'ultimo': j['finished_at'], 'snapshot': j.get('snapshot'), 'horas': round((dt.datetime.now(fim.tzinfo) - fim).total_seconds() / 3600, 1)}
    except Exception as e:  # noqa: BLE001
        return {'erro': str(e)[:120], 'horas': 9999}


# ------------------------------------------------------------------ banco e Kuma
ESQUEMA = """create schema if not exists plataforma;
create table if not exists plataforma.saude_amostras (ts timestamptz primary key default now(), dados jsonb not null);"""


def gravar(amostra):
    js = json.dumps(amostra).replace("'", "''")
    psql(ESQUEMA, db='produtos')
    psql(f"insert into plataforma.saude_amostras(ts,dados) values (now(), '{js}'::jsonb); "
         "delete from plataforma.saude_amostras where ts < now() - interval '90 days'", db='produtos')


def anterior():
    out = psql("select extract(epoch from ts), dados::text from plataforma.saude_amostras order by ts desc limit 1", db='produtos')
    if not out:
        return None
    t, d = out.split('|', 1)
    return float(t), json.loads(d)


def avisar(tokens, sinal, ok, msg):
    tk = tokens.get('KUMA_PUSH_' + sinal.upper().replace('-', '_'))
    if not tk:
        return
    q = urllib.parse.urlencode({'status': 'up' if ok else 'down', 'msg': msg[:200], 'ping': ''})
    try:
        urllib.request.urlopen(urllib.request.Request(KUMA + tk + '?' + q, headers=UA), timeout=20).read()
    except Exception as e:  # noqa: BLE001
        print('kuma push falhou', sinal, e, file=sys.stderr)


def main(sem_push=False):
    inicio = time.time()
    try:
        ant = anterior()
    except Exception:  # noqa: BLE001
        ant = None
    a = {'disco': ler_disco(), 'backup': ler_backup()}
    for nome, f in (('postgres', ler_postgres), ('minio', ler_minio)):
        try:
            a[nome] = f()
        except Exception as e:  # noqa: BLE001
            a[nome] = {'erro': str(e)[:200]}
    if ant:  # taxas pela diferença entre amostras
        dtempo = max(1.0, time.time() - ant[0])
        p0, m0 = ant[1].get('postgres', {}), ant[1].get('minio', {})
        if 'transacoes' in a['postgres'] and 'transacoes' in p0:
            a['postgres']['tps'] = round((a['postgres']['transacoes'] - p0['transacoes']) / dtempo, 2)
        if 'requisicoes' in a['minio'] and 'requisicoes' in m0:
            dreq = a['minio']['requisicoes'] - m0['requisicoes']
            a['minio']['req_s'] = round(dreq / dtempo, 3)
            a['minio']['erros_5xx_pct'] = round(100 * (a['minio']['erros_5xx'] - m0.get('erros_5xx', 0)) / dreq, 2) if dreq > 0 else 0.0
    a['coletado_em'] = dt.datetime.now().astimezone().isoformat(timespec='seconds')
    a['duracao_s'] = round(time.time() - inicio, 1)
    gravar(a)
    if sem_push:
        print(json.dumps(a, ensure_ascii=False)[:1500])
        return
    tokens = infisical('plataforma', 'uptime-kuma')
    pg, mn, dk, bk = a['postgres'], a['minio'], a['disco'], a['backup']
    avisar(tokens, 'disco', dk['pct'] < LIM['disco_pct'], f"disco {dk['pct']}% ({dk['livre_gb']} GB livres)")
    avisar(tokens, 'postgres-conexoes', 'erro' not in pg and pg['conexoes_pct'] < LIM['pg_conexoes_pct'], f"conexoes {pg.get('conexoes')}/{pg.get('max_conexoes')} {pg.get('erro', '')}")
    avisar(tokens, 'postgres-cache', 'erro' not in pg and pg['cache_pct'] >= LIM['pg_cache_pct'], f"cache {pg.get('cache_pct')}%")
    avisar(tokens, 'postgres-transacao-longa', 'erro' not in pg and pg['tx_mais_longa_s'] < LIM['pg_tx_longa_s'], f"transacao mais longa {pg.get('tx_mais_longa_s')} s")
    avisar(tokens, 'minio-pronto', bool(mn.get('pronto')), 'pronto' if mn.get('pronto') else f"MinIO fora: {mn.get('erro', 'ready falhou')}")
    avisar(tokens, 'minio-erros', mn.get('erros_5xx_pct', 0) < LIM['minio_erros_5xx_pct'], f"5xx {mn.get('erros_5xx_pct', 0)}% ({mn.get('req_s', 0)} req/s)")
    avisar(tokens, 'backup-idade', bk['horas'] < LIM['backup_horas'], f"ultimo backup ha {bk['horas']} h")
    avisar(tokens, 'coletor', True, f"amostra gravada em {a['duracao_s']} s")
    print('ok', a['coletado_em'], f"disco {dk['pct']}%", f"pg {pg.get('conexoes')}/{pg.get('max_conexoes')}", f"minio pronto={mn.get('pronto')}")


if __name__ == '__main__':
    main('--sem-push' in sys.argv)
