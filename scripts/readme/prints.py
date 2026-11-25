"""Prints de produção para o README (spec 57 §3.2 b): depois de um deploy, abre o produto num navegador de verdade e grava
docs/img/landing.webp (página inicial) e docs/img/admin.webp (/admin) no repositório do produto. Roda no fim do deploy.yml.
Uso: python3 scripts/readme/prints.py <servico> <pasta-de-saida>   -> imprime o repositório e os arquivos gerados (JSON)"""
import json
import os
import sys

import yaml
from PIL import Image
from playwright.sync_api import sync_playwright

servico, saida = sys.argv[1], sys.argv[2]
RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
reg = yaml.safe_load(open(os.path.join(RAIZ, 'registro', 'produtos.yml'), encoding='utf-8'))['produtos']
itens = [x for x in reg if x.get('servico') == servico and x.get('tipo') in ('produto', 'em_teste') and x.get('hosts')]
if not itens:
    print(json.dumps({'repo': None, 'motivo': 'serviço sem página de produto no registro'}))
    sys.exit(0)
p = itens[0]
host = p['hosts'][0]
os.makedirs(saida, exist_ok=True)
gerados = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={'width': 1280, 'height': 800}, device_scale_factor=1)
    for nome, caminho in (('landing', '/'), ('admin', '/admin')):
        try:
            pg.goto(f'https://{host}{caminho}', wait_until='networkidle', timeout=45000)
            pg.wait_for_timeout(2500)
            png = os.path.join(saida, f'{nome}.png')
            pg.screenshot(path=png)
            Image.open(png).convert('RGB').save(os.path.join(saida, f'{nome}.webp'), quality=82, method=6)
            os.remove(png)
            gerados.append(f'docs/img/{nome}.webp')
        except Exception as e:  # noqa: BLE001  um print que falha não derruba o outro nem o deploy
            print(f'aviso: {nome} falhou: {e}', file=sys.stderr)
    b.close()
print(json.dumps({'repo': p['repositorio'], 'host': host, 'arquivos': gerados}))
