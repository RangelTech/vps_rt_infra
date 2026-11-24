"""Importa UM arquivo de segredo da VPS para o Infisical, COPIANDO o valor atual (nada e trocado) e conferindo 1 a 1.
Uso: importar.py <projeto> <caminho-na-vps> <pasta> [env|bloco]
  env   : arquivo KEY=VALOR -> uma entrada por variavel
  bloco : arquivo inteiro (chave privada, rclone.conf...) -> uma unica entrada CONTEUDO
Nunca imprime valor. Nao sobrescreve segredo existente."""
import sys, subprocess, json, os, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from infapi import call, token
projetos = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'infisical_projetos.json')))
proj, caminho, pasta = sys.argv[1], sys.argv[2], sys.argv[3]
modo = sys.argv[4] if len(sys.argv) > 4 else 'env'
PID = projetos[proj]; ENV = 'prod'
ssh = ['ssh', '-i', os.path.expanduser('~/.ssh/vps_rt_infra_deploy_v3'), 'deploy@66.94.101.153']
raw = subprocess.run(ssh + ['sudo -n cat ' + caminho], capture_output=True, text=True, encoding='utf-8', timeout=60)
assert raw.returncode == 0, 'falha ao ler ' + caminho
vars_ = {}; ordem = []
if modo == 'bloco':
    vars_['CONTEUDO'] = raw.stdout; ordem = ['CONTEUDO']
else:
    for ln in raw.stdout.splitlines():
        if not ln.strip() or ln.lstrip().startswith('#') or '=' not in ln: continue
        k, v = ln.split('=', 1); k = k.strip()
        if not k.replace('_', '').isalnum(): continue
        vars_[k] = v; ordem.append(k)
tok = token()
call('/api/v1/folders', {'workspaceId': PID, 'environment': ENV, 'name': pasta, 'path': '/'}, tok)
base = f'/api/v3/secrets/raw?workspaceId={PID}&environment={ENV}&secretPath=/{pasta}'
exist = {s['secretKey'] for s in call(base, tok=tok).get('secrets', [])}
novos = [{'secretKey': k, 'secretValue': vars_[k]} for k in ordem if k not in exist]
if novos:
    r = call('/api/v3/secrets/batch/raw', {'workspaceId': PID, 'environment': ENV, 'secretPath': f'/{pasta}', 'secrets': novos}, tok)
    assert 'secrets' in r, str(r)[:200]
dep = {s['secretKey']: s['secretValue'] for s in call(base, tok=tok).get('secrets', [])}
faltam = [k for k in vars_ if k not in dep]
def _igual(x, y):
    return x == y or (modo == 'bloco' and x.rstrip() == y.rstrip())   # bloco: so espaco/linha em branco no fim pode variar (o Infisical normaliza)
diferem = [k for k in vars_ if k in dep and not _igual(dep[k], vars_[k])]
ok = not faltam and not diferem
print(f'{proj}/{pasta}: {len(vars_) - len(faltam) - len(diferem)} de {len(vars_)} batem' + ('' if ok else f' | FALTAM={faltam} DIFEREM={diferem}'))
ev = os.path.join(os.environ.get('EVIDENCIAS_DIR', r'C:/Users/lucas.rangel/Desktop/new_ragente/qa/evidencias'), datetime.date.today().strftime('%Y%m%d') + f'-item0-{proj}-{pasta}')
os.makedirs(ev, exist_ok=True)
open(os.path.join(ev, 'resultado.md'), 'w', encoding='utf-8').write(
f"""# Item 0 (fundação): {pasta} para o Infisical ({proj})
- Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')} | Origem: `{caminho}` ({modo}) | Destino: projeto `{proj}`, ambiente `{ENV}`, pasta `/{pasta}`
- Variáveis (só nomes): {', '.join(ordem)}
- Lidas: {len(vars_)} | Batem 1 a 1: {len(vars_) - len(faltam) - len(diferem)} | Faltam: {faltam or 'nenhuma'} | Diferem: {diferem or 'nenhuma'}
- Nenhum valor foi trocado (R5). Resultado: **{'PASSOU' if ok else 'FALHOU'}**
""")
sys.exit(0 if ok else 1)
