"""Portão do README (spec 57 §3.2): o CI de todo repositório da organização roda isto e FALHA se faltar o README, uma das
partes obrigatórias ou o print. Em repositório de produto confere também o checklist da §3 (segredos.yml, .env.example,
planos.json). Uso (no CI do repositório): python3 conferir_readme.py [pasta]   (padrão: pasta atual)
Baixado de https://raw.githubusercontent.com/RangelTech/vps_rt_infra/main/scripts/readme/conferir_readme.py"""
import os
import re
import sys

RAIZ = sys.argv[1] if len(sys.argv) > 1 else '.'
PARTES = {
    'o que é': r'o que [eé]|sobre|vis[aã]o geral',
    'onde está no ar': r'no ar|endere[cç]o|produ[cç][aã]o|https?://[a-z0-9.-]+\.(rangeltech\.net|segundocerebro\.pro)',
    'onde faz o deploy': r'deploy',
    'como funciona por dentro': r'como funciona|arquitetura|por dentro',
    'segredos (onde ficam, nunca valores)': r'segredo|infisical|\.env',
    'como rodar e testar': r'test|rodar local|localmente|pytest|npm (run )?test',
    'dono e links': r'dono|spec|kuma|monitor|painel',
}
erros = []
f = os.path.join(RAIZ, 'README.md')
if not os.path.exists(f):
    print('FALHA: o repositório não tem README.md (spec 57 §3.2)')
    sys.exit(1)
txt = open(f, encoding='utf-8').read()
for parte, rx in PARTES.items():
    if not re.search(rx, txt, re.I):
        erros.append(f'falta a parte "{parte}"')
imgs = [a or b for a, b in re.findall(r'!\[[^\]]*\]\(([^)\s]+)\)|<img [^>]*src="([^"]+)"', txt)]
locais = [i for i in imgs if not i.startswith('http')]
if not imgs:
    erros.append('falta pelo menos um print (docs/img/...)')
for i in locais:
    if not os.path.exists(os.path.join(RAIZ, i.split('?')[0].split('#')[0].lstrip('./'))):
        erros.append(f'print citado e inexistente: {i}')
PLACEHOLDER = re.compile(r'(?i)your|change|exemplo|example|xxx|placeholder|default|endpoint-proxy|seu-|sua-')
for m in re.finditer(r'(?i)(senha|password|secret|token)\s*[:=]\s*["\']?([A-Za-z0-9_\-]{16,})', txt):
    if not PLACEHOLDER.search(m.group(2)):
        erros.append(f'parece haver um valor de segredo no README (linha com {m.group(1)})')
if os.path.exists(os.path.join(RAIZ, 'segredos.yml')) and not os.path.exists(os.path.join(RAIZ, '.env.example')):
    erros.append('tem segredos.yml mas não tem .env.example (só nomes)')


def vende_planos(nome: str) -> bool:
    """Produto à venda no registro único (vps_rt_infra/registro/produtos.yml): exige planos.json (spec 57 §3 item 4)."""
    import urllib.request
    try:
        reg = urllib.request.urlopen('https://raw.githubusercontent.com/RangelTech/vps_rt_infra/main/registro/produtos.yml', timeout=20).read().decode()
    except Exception:  # noqa: BLE001  sem rede: não bloqueia por isso
        return False
    return any(re.search(r'tipo:\s*produto', l) and f'RangelTech/{nome},' in l.replace(' ', '') + ',' for l in reg.splitlines())


NOME = (os.environ.get('GITHUB_REPOSITORY') or os.path.abspath(RAIZ)).replace(os.sep, '/').rstrip('/').split('/')[-1]
if vende_planos(NOME) and not os.path.exists(os.path.join(RAIZ, 'planos.json')):
    erros.append('produto sem planos.json (contrato de planos, spec 57 §3 item 4)')
if erros:
    print('README fora do padrão (spec 57 §3.2):\n  - ' + '\n  - '.join(erros))
    sys.exit(1)
print(f'README ok: {len(PARTES)} partes, {len(imgs)} print(s)')
