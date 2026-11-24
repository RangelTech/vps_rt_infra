"""Gera o .env de UM servico a partir do Infisical, NO MOMENTO DO DEPLOY (spec 57, 0A.2 item 4).
Uso: render_env.py <projeto> <pasta> <destino> [env|bloco]
Credencial: INFISICAL_ENV_FILE (identidade SOMENTE LEITURA). Escreve o destino de forma atomica (modo 600) e so se ler tudo;
se o Infisical estiver fora do ar ou a pasta vier vazia, SAI COM ERRO sem tocar no arquivo atual. Nunca imprime valor."""
import sys, os, json, re, urllib.request, tempfile
here = os.path.dirname(os.path.abspath(__file__))
projetos = json.load(open(os.path.join(here, 'infisical_projetos.json')))
proj, pasta, destino = sys.argv[1], sys.argv[2], sys.argv[3]
modo = sys.argv[4] if len(sys.argv) > 4 else 'env'
cfg = {}
for l in open(os.environ.get('INFISICAL_ENV_FILE', os.path.expanduser('~/.claude/secrets/infisical-rt-deploy-leitura.env')), encoding='utf-8'):
    m = re.match(r'^([A-Z_]+)=(.*)$', l.rstrip('\r\n'))
    if m: cfg[m.group(1)] = m.group(2)
def call(path, body=None, tok=None):
    h = {'User-Agent': 'curl/8.5.0', 'Content-Type': 'application/json'}
    if tok: h['Authorization'] = 'Bearer ' + tok
    r = urllib.request.Request(cfg['INFISICAL_URL'] + path, data=json.dumps(body).encode() if body is not None else None, headers=h)
    return json.load(urllib.request.urlopen(r, timeout=30))
try:
    tok = call('/api/v1/auth/universal-auth/login', {'clientId': cfg['INFISICAL_CLIENT_ID'], 'clientSecret': cfg['INFISICAL_CLIENT_SECRET']})['accessToken']
    sec = call(f"/api/v3/secrets/raw?workspaceId={projetos[proj]}&environment=prod&secretPath=/{pasta}", tok=tok)['secrets']
except Exception as e:
    print('ERRO: Infisical indisponivel ou sem acesso; arquivo atual mantido:', type(e).__name__); sys.exit(2)
if not sec:
    print('ERRO: pasta vazia no Infisical; arquivo atual mantido'); sys.exit(3)
if modo == 'bloco':
    texto = {s['secretKey']: s['secretValue'] for s in sec}['CONTEUDO'].rstrip() + '\n'
else:
    texto = ''.join(f"{s['secretKey']}={s['secretValue']}\n" for s in sec)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(destino)) or '.')
with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f: f.write(texto)
try: os.chmod(tmp, 0o600)
except Exception: pass
os.replace(tmp, destino)
print(f'ok: {proj}/{pasta} -> {destino} ({len(sec)} entradas)')
