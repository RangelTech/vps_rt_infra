"""MinIO oficial dos produtos (spec 57 §8.6): um bucket, um usuário e uma política mínima por produto. Idempotente.

- bucket <produto> (sem expiração: ordem de 24/11);
- política <produto>-rw: só o bucket dele (listar, ler, gravar, apagar);
- usuário <produto>-svc com essa política. A chave secreta é criada UMA vez e guardada no Infisical
  (rt-produtos/<produto>/S3_*). Se já existe no Infisical, é reaplicada igual (nunca troca: regra de não rotacionar).
Uso (máquina com o cofre e ssh na VPS): py -3 scripts/minio/provisionar.py <produto> [<produto>...]
"""
import json
import os
import secrets
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, '..', 'infisical'))
from infapi import call, token  # noqa: E402

P = json.load(open(os.path.join(AQUI, '..', 'infisical', 'infisical_projetos.json'), encoding='utf-8'))
SSH = ['ssh', '-i', os.path.expanduser('~/.ssh/vps_rt_infra_deploy_v3'), 'deploy@66.94.101.153']
ENDPOINT = 'http://minio:9000'  # rede interna do Docker; nada sai pela internet


def mc(script: str) -> str:
    """Roda comandos mc dentro do contêiner do MinIO (alias 'local' com a credencial de root que já está nele)."""
    cmd = 'mc alias set local http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null && ' + script
    r = subprocess.run(SSH + ['docker exec -i minio sh -s'], input=cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f'mc falhou: {r.stderr.strip()[-400:]}')
    return r.stdout


def politica(bucket: str) -> str:
    return json.dumps({"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": ["s3:GetBucketLocation", "s3:ListBucket", "s3:ListBucketMultipartUploads"],
         "Resource": [f"arn:aws:s3:::{bucket}"]},
        {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload",
                                       "s3:ListMultipartUploadParts"], "Resource": [f"arn:aws:s3:::{bucket}/*"]}]})


def provisionar(p: str, tok: str) -> None:
    base = f"/api/v3/secrets/raw?workspaceId={P['rt-produtos']}&environment=prod&secretPath=/{p}"
    atual = {s['secretKey']: s['secretValue'] for s in call(base, tok=tok)['secrets']}
    usuario = atual.get('S3_ACCESS_KEY') or f'{p}-svc'
    senha = atual.get('S3_SECRET_KEY') or secrets.token_urlsafe(30)
    # grava no Infisical ANTES de criar o usuário: se o mc cair no meio, a próxima rodada usa a mesma chave
    novos = [{'secretKey': k, 'secretValue': v} for k, v in
             (('S3_ENDPOINT', ENDPOINT), ('S3_BUCKET', p), ('S3_ACCESS_KEY', usuario), ('S3_SECRET_KEY', senha)) if k not in atual]
    if novos:
        r = call('/api/v3/secrets/batch/raw', {'workspaceId': P['rt-produtos'], 'environment': 'prod', 'secretPath': f'/{p}', 'secrets': novos}, tok)
        assert 'secrets' in r, r
    pol = politica(p).replace("'", "'\\''")
    mc(f"mc mb --ignore-existing local/{p} >/dev/null && "
       f"printf '%s' '{pol}' > /tmp/pol-{p}.json && mc admin policy create local {p}-rw /tmp/pol-{p}.json >/dev/null && rm /tmp/pol-{p}.json && "
       f"(mc admin user info local '{usuario}' >/dev/null 2>&1 || mc admin user add local '{usuario}' '{senha}' >/dev/null) && "
       f"mc admin policy attach local {p}-rw --user '{usuario}' >/dev/null 2>&1; mc admin user info local '{usuario}' --json")
    print(f'{p}: bucket, política {p}-rw e usuário {usuario} prontos; Infisical: {"gravado " + ",".join(n["secretKey"] for n in novos) if novos else "já tinha"}')


if __name__ == '__main__':
    t = token()
    for prod in sys.argv[1:]:
        provisionar(prod, t)
