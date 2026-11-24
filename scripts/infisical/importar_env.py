"""Importa o .env de um produto da VPS para o Infisical (projeto rt-produtos, ambiente prod, pasta /<produto>),
COPIANDO o valor atual (nada e trocado) e conferindo 1 a 1. Nunca imprime valor de segredo."""
import sys, subprocess, hashlib, json, os, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from infapi import call, token
PID = '963e2bf6-c5e4-4fa2-a3f1-3330fa2a27c6'   # rt-produtos
ENV = 'prod'
produto = sys.argv[1]
ssh = ['ssh', '-i', os.path.expanduser('~/.ssh/vps_rt_infra_deploy_v3'), 'deploy@66.94.101.153']
raw = subprocess.run(ssh + ['sudo -n cat /opt/platform/secrets/%s.env' % produto], capture_output=True, text=True, timeout=60)
assert raw.returncode == 0, 'falha ao ler o .env da VPS'
vars_ = {}
ordem = []
for ln in raw.stdout.splitlines():
    if not ln.strip() or ln.lstrip().startswith('#') or '=' not in ln:
        continue
    k, v = ln.split('=', 1)
    k = k.strip()
    if not k.replace('_', '').isalnum():
        continue
    vars_[k] = v        # valor cru, exatamente como esta no arquivo
    ordem.append(k)
print(f'[{produto}] variaveis lidas da VPS: {len(vars_)}')
tok = token()
# pasta
f = call('/api/v1/folders', {'workspaceId': PID, 'environment': ENV, 'name': produto, 'path': '/'}, tok)
print('pasta:', 'criada' if 'folder' in f else str(f)[:120])
# segredos (cria os que faltam; nao sobrescreve nenhum existente)
atual = call(f'/api/v3/secrets/raw?workspaceId={PID}&environment={ENV}&secretPath=/{produto}', tok=tok)
existentes = {s['secretKey'] for s in atual.get('secrets', [])}
novos = [{'secretKey': k, 'secretValue': vars_[k]} for k in ordem if k not in existentes]
if novos:
    r = call('/api/v3/secrets/batch/raw', {'workspaceId': PID, 'environment': ENV, 'secretPath': f'/{produto}', 'secrets': novos}, tok)
    print('criados:', len(novos) if 'secrets' in r else str(r)[:200])
else:
    print('nada a criar (ja existiam)')
# conferencia 1 a 1
dep = call(f'/api/v3/secrets/raw?workspaceId={PID}&environment={ENV}&secretPath=/{produto}', tok=tok)
no_inf = {s['secretKey']: s['secretValue'] for s in dep.get('secrets', [])}
faltam = [k for k in vars_ if k not in no_inf]
diferem = [k for k in vars_ if k in no_inf and no_inf[k] != vars_[k]]
extras = [k for k in no_inf if k not in vars_]
ok = not faltam and not diferem
print(f'conferencia: {len(vars_) - len(faltam) - len(diferem)} de {len(vars_)} batem | faltam={faltam} | diferem={diferem} | extras={extras}')
ev = os.path.join(os.environ.get('EVIDENCIAS_DIR', r'C:/Users/lucas.rangel/Desktop/new_ragente/qa/evidencias'), datetime.date.today().strftime('%Y%m%d') + f'-item0-{produto}')
os.makedirs(ev, exist_ok=True)
open(os.path.join(ev, 'resultado.md'), 'w', encoding='utf-8').write(
f"""# Item 0 (fundação): {produto} para o Infisical

- Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}
- Origem: `/opt/platform/secrets/{produto}.env` (VPS). Destino: Infisical, projeto `rt-produtos`, ambiente `{ENV}`, pasta `/{produto}`.
- Variáveis (só nomes): {', '.join(ordem)}
- Lidas: {len(vars_)} | No Infisical depois: {len(no_inf)} | Batem 1 a 1: {len(vars_) - len(faltam) - len(diferem)}
- Faltam: {faltam or 'nenhuma'} | Diferem: {diferem or 'nenhuma'} | Extras no Infisical: {extras or 'nenhuma'}
- Nenhum valor foi trocado (R5): o Infisical recebeu cópia do valor atual. Nenhum valor aparece neste relatório.
- Resultado: **{'PASSOU' if ok else 'FALHOU'}**
""")
sys.exit(0 if ok else 1)
