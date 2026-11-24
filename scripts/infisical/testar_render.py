"""Teste da fundacao: o .env GERADO a partir do Infisical e semanticamente IGUAL ao arquivo atual da VPS (mesmas variaveis, mesmos valores)."""
import subprocess, os, sys, tempfile, datetime
S = '/opt/platform/secrets/'
ITENS = [('rt-produtos', p, S + p + '.env', 'env') for p in 'arenabruta boateazul astralai casaai shapeai rendai cortai animaai postaai perfilai atendeai viralizai'.split()]
ITENS += [('rt-produtos', 'perfil-navegador', S + 'perfil-navegador.env', 'env'), ('rt-produtos', '_admin', S + 'rt-admin.env', 'env')]
ITENS += [('qwen', n, S + n + '.env', 'env') for n in ('llm-access', 'llm-queue', 'llm-gateway', 'gateway-keys')]
ITENS += [('segundo-cerebro', 'segundo-cerebro-remoto', S + 'segundo-cerebro-remoto.env', 'env')]
ITENS += [('luar', n, S + n + '.env', 'env') for n in 'agent-platform-backend canais chatwoot-bridge chatwoot-rails kernel-harness luar-conector-hub rt-canais rt-gateway rt-hermes rt-hermes-produtos runtime-manager'.split()]
ITENS += [('plataforma', n, S + n + '.env', 'env') for n in ('ai-aluno-turn', 'portfolio-api', 'proxy-sp', 'restic')]
ITENS += [('plataforma', 'rclone', S + 'rclone.conf', 'bloco'), ('plataforma', 'airflow-pessoal-deploy-key', S + 'airflow_pessoal_deploy_key', 'bloco'), ('plataforma', 'compose', '/opt/platform/compose/.env', 'env')]
ssh = ['ssh', '-i', os.path.expanduser('~/.ssh/vps_rt_infra_deploy_v3'), 'deploy@66.94.101.153']
def parse(t):
    d = {}
    for ln in t.splitlines():
        if not ln.strip() or ln.lstrip().startswith('#') or '=' not in ln: continue
        k, v = ln.split('=', 1)
        if k.strip().replace('_', '').isalnum(): d[k.strip()] = v
    return d
res = []; falhas = 0
tmp = tempfile.mkdtemp()
for proj, pasta, caminho, modo in ITENS:
    dest = os.path.join(tmp, proj + '__' + pasta)
    r = subprocess.run([sys.executable, 'render_env.py', proj, pasta, dest, modo], capture_output=True, text=True)
    if r.returncode != 0:
        res.append((proj, pasta, 'ERRO ao gerar: ' + r.stdout.strip()[:80])); falhas += 1; continue
    orig = subprocess.run(ssh + ['sudo -n cat ' + caminho], capture_output=True, text=True).stdout
    novo = open(dest, encoding='utf-8').read()
    igual = (orig.rstrip() == novo.rstrip()) if modo == 'bloco' else (parse(orig) == parse(novo))
    res.append((proj, pasta, 'igual' if igual else 'DIFERENTE'))
    falhas += 0 if igual else 1
ok = len(res) - falhas
print(f'{ok} de {len(res)} arquivos gerados do Infisical sao IGUAIS aos da VPS')
for p, n, st in res:
    if st != 'igual': print('  ->', p, n, st)
ev = os.environ.get('EVIDENCIAS_DIR', r'C:/Users/lucas.rangel/Desktop/new_ragente/qa/evidencias') + '/' + datetime.date.today().strftime('%Y%m%d') + '-item0-render'
os.makedirs(ev, exist_ok=True)
open(ev + '/resultado.md', 'w', encoding='utf-8').write('# Item 0: .env gerado do Infisical x arquivo da VPS\n\n- ' + datetime.datetime.now().strftime('%d/%m/%Y %H:%M') + f'\n- Identidade de leitura (viewer). Iguais: **{ok} de {len(res)}**\n\n| Projeto | Pasta | Resultado |\n|---|---|---|\n' + ''.join(f'| {p} | {n} | {st} |\n' for p, n, st in res) + '\nResultado: **' + ('PASSOU' if falhas == 0 else 'FALHOU') + '**\n')
sys.exit(1 if falhas else 0)
