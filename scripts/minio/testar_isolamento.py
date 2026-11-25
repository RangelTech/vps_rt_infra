"""Prova (spec 57 §8.6): a chave de cada produto grava, lê, lista e apaga no próprio bucket e é NEGADA no bucket de outro.
Uso: py -3 scripts/minio/testar_isolamento.py <produto> [<produto>...]   (o 'outro' é o próximo da lista; com um só, usa 'viralizai')"""
import json
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, '..', 'infisical'))
from infapi import call, token  # noqa: E402

P = json.load(open(os.path.join(AQUI, '..', 'infisical', 'infisical_projetos.json'), encoding='utf-8'))
SSH = ['ssh', '-i', os.path.expanduser('~/.ssh/vps_rt_infra_deploy_v3'), 'deploy@66.94.101.153']


def chaves(p, tok):
    s = {x['secretKey']: x['secretValue'] for x in call(f"/api/v3/secrets/raw?workspaceId={P['rt-produtos']}&environment=prod&secretPath=/{p}", tok=tok)['secrets']}
    return s['S3_ACCESS_KEY'], s['S3_SECRET_KEY']


def testar(p, outro, tok):
    u, k = chaves(p, tok)
    script = f"""set +e
mc alias set eu http://127.0.0.1:9000 '{u}' '{k}' >/dev/null || {{ echo "LOGIN_FALHOU"; exit 0; }}
echo teste-{p} | mc pipe eu/{p}/_teste/isolamento.txt >/dev/null && echo GRAVA_OK
[ "$(mc cat eu/{p}/_teste/isolamento.txt)" = "teste-{p}" ] && echo LE_OK
mc ls eu/{p}/_teste/ >/dev/null && echo LISTA_OK
mc rm eu/{p}/_teste/isolamento.txt >/dev/null && echo APAGA_OK
mc ls eu/{outro}/ >/dev/null 2>&1 && echo OUTRO_LISTA_PERMITIDO
echo x | mc pipe eu/{outro}/_invasao.txt >/dev/null 2>&1 && echo OUTRO_GRAVA_PERMITIDO
mc alias rm eu >/dev/null"""
    r = subprocess.run(SSH + ['docker exec -i minio sh -s'], input=script.encode(), capture_output=True).stdout.decode()  # bytes: sem CR do Windows
    ok = all(x in r for x in ('GRAVA_OK', 'LE_OK', 'LISTA_OK', 'APAGA_OK')) and 'PERMITIDO' not in r
    print(f"{p}: {' '.join(r.split())} -> {'PASSOU' if ok else 'FALHOU'}")
    return ok


if __name__ == '__main__':
    t = token(); ps = sys.argv[1:]
    res = [testar(p, ps[(i + 1) % len(ps)] if len(ps) > 1 else 'viralizai', t) for i, p in enumerate(ps)]
    sys.exit(0 if all(res) else 1)
