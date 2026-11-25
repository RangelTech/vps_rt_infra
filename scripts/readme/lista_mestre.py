"""Lista mestre dos repositórios da organização (spec 57 §3.2 c), gravada no README do vps_rt_infra entre as marcas
<!-- repos:inicio --> e <!-- repos:fim -->. Fonte: `gh repo list`, o README de cada repositório (parte "O que é") e o registro
único (registro/produtos.yml). Uso: py -3 scripts/readme/lista_mestre.py   (precisa do gh logado)"""
import base64
import json
import os
import re
import subprocess

import yaml

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, '..', '..')
NUNCA = {'capitalcerto_lake', 'data-ia-hub', 'skills-capital-certo'}  # Capital Certo: fora da plataforma


def gh(*a):
    r = subprocess.run(['gh', *a], capture_output=True, text=True, encoding='utf-8')
    return r.stdout if r.returncode == 0 else ''


reg = yaml.safe_load(open(os.path.join(RAIZ, 'registro', 'produtos.yml'), encoding='utf-8'))['produtos']
por_repo = {}
for x in reg:
    nome = (x.get('repositorio') or '').split('/')[-1]
    if nome:
        por_repo.setdefault(nome, []).append(x)
repos = json.loads(gh('repo', 'list', 'RangelTech', '-L', '200', '--json', 'name,description,visibility,isArchived'))
linhas = ['| Repositório | O que é | Estado | No ar | Deploy (`service=`) |', '|---|---|---|---|---|']
for r in sorted(repos, key=lambda x: x['name']):
    n = r['name']
    if n in NUNCA:
        continue
    desc = (r.get('description') or '').strip()
    try:
        txt = base64.b64decode(json.loads(gh('api', f'repos/RangelTech/{n}/readme'))['content']).decode('utf-8', 'replace')
        m = re.search(r'(?im)^##\s*O que [eé][^\n]*\n+([^\n#]+)', txt)
        if m:
            desc = re.sub(r'[*`]', '', m.group(1)).strip()
    except Exception:  # noqa: BLE001
        pass
    desc = re.split(r'(?<=[.!?])\s', desc)[0][:140].replace('|', '/')
    itens = por_repo.get(n, [])
    estado = 'arquivado' if r['isArchived'] else ({'produto': 'no ar', 'variante': 'no ar', 'em_teste': 'em teste', 'em_preparo': 'em preparo'}
                                                 .get(itens[0]['tipo'], 'no ar') if itens else 'ver README')
    hosts = sorted({h for x in itens for h in (x.get('hosts') or [])})[:3]
    servicos = sorted({x.get('servico') for x in itens if x.get('servico')})
    linhas.append(f"| [{n}](https://github.com/RangelTech/{n}){' (privado)' if r['visibility'] == 'PRIVATE' else ''} | {desc or '-'} | {estado} | "
                  f"{', '.join(hosts) or '-'} | {', '.join(f'`{s}`' for s in servicos) or '-'} |")
bloco = '<!-- repos:inicio -->\n## Repositórios da organização\n\nGerado por `scripts/readme/lista_mestre.py` (não editar à mão). Todo repositório tem README no padrão da casa (spec 57 §3.2), conferido no CI pelo `scripts/readme/conferir_readme.py`. Capital Certo fica fora.\n\n' + '\n'.join(linhas) + '\n<!-- repos:fim -->'
f = os.path.join(RAIZ, 'README.md')
s = open(f, encoding='utf-8').read()
if '<!-- repos:inicio -->' in s:
    s = re.sub(r'<!-- repos:inicio -->.*?<!-- repos:fim -->', lambda _: bloco, s, flags=re.S)
else:
    i = s.find('\n## Notas técnicas')
    s = s[:i] + '\n\n' + bloco + '\n' + s[i:] if i > 0 else s + '\n\n' + bloco + '\n'
open(f, 'w', encoding='utf-8', newline='\n').write(s)
print(len(linhas) - 2, 'repositórios na lista')
