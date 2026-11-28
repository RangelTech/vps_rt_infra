"""Exporta o registro único (registro/produtos.yml) para o painel (spec 57 §6.2A): só nomes, endereços e caminhos, nunca
segredo. Grava em <qwen-abliterated-api>/access/app/registro_produtos.json. Uso: py -3 scripts/registro/exportar_painel.py <pasta-do-qwen>"""
import json
import os
import sys

import yaml

AQUI = os.path.dirname(os.path.abspath(__file__))
reg = yaml.safe_load(open(os.path.join(AQUI, '..', '..', 'registro', 'produtos.yml'), encoding='utf-8'))
fontes = {s['service']: s for s in json.load(open(os.path.join(AQUI, '..', '..', 'releases', 'sources.json'), encoding='utf-8'))['sources']}
out = []
for x in reg['produtos']:
    host = (x.get('hosts') or [''])[0]
    repo = x.get('repositorio', '')
    out.append({
        'id': x['id'], 'nome': x['nome'], 'tipo': x['tipo'], 'base': x.get('base'), 'schema': x.get('schema'), 'banco': x.get('banco'),
        'servico': x.get('servico'), 'hosts': x.get('hosts') or [], 'cakto': x.get('cakto') or [],
        'links': {
            'produto': f'https://{host}/' if host else None,
            'admin': f'https://{host}/admin' if host and x['tipo'] in ('produto', 'variante', 'em_teste') else None,
            'github': f'https://github.com/{repo}' if repo else None,
            'readme': f'https://github.com/{repo}#readme' if repo else None,
            'deploy': 'https://github.com/RangelTech/vps_rt_infra/actions/workflows/deploy.yml' if x.get('servico') in fontes else None,
            'release': f'https://github.com/{repo}/actions' if repo else None,
            'monitor': 'https://uptime.rangeltech.net/status/rangeltech',
        },
        'qa': x.get('qa'),
    })
destino = os.path.join(sys.argv[1], 'access', 'app', 'registro_produtos.json')
json.dump({'gerado_de': 'RangelTech/vps_rt_infra registro/produtos.yml', 'atualizado': reg.get('atualizado'), 'produtos': out},
          open(destino, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(len(out), 'entradas ->', destino)
