"""Valida registro/produtos.yml (spec 57, §10A.1). Sai com erro se algo estiver fora do padrão.
Verifica: campos obrigatórios, ids e hosts únicos, `servico` existe em releases/sources.json (exceto em_preparo sem release),
variantes apontam para um produto base existente, contas Cakto conhecidas, nenhum valor de segredo no arquivo."""
import json, os, re, sys
import yaml

raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
reg = yaml.safe_load(open(os.path.join(raiz, 'registro', 'produtos.yml'), encoding='utf-8'))
srcs = {s['service'] for s in json.load(open(os.path.join(raiz, 'releases', 'sources.json'), encoding='utf-8'))['sources']}
erros = []
ids, hosts = set(), {}
contas = set(reg.get('contas_cakto', {}))
bases = {p['id'] for p in reg['produtos'] if p.get('tipo') in ('produto', 'plataforma', 'em_preparo')}
for p in reg['produtos']:
    for campo in ('id', 'nome', 'tipo', 'servico', 'repositorio', 'hosts'):
        if not p.get(campo):
            erros.append(f"{p.get('id', '?')}: falta o campo '{campo}'")
    if p.get('id') in ids:
        erros.append(f"id repetido: {p['id']}")
    ids.add(p.get('id'))
    for h in p.get('hosts', []):
        if h in hosts:
            erros.append(f"host repetido: {h} ({p['id']} e {hosts[h]})")
        hosts[h] = p['id']
    if p.get('tipo') == 'variante' and p.get('base') not in bases:
        erros.append(f"{p['id']}: variante sem produto base válido ({p.get('base')})")
    for c in p.get('cakto', []):
        if c not in contas:
            erros.append(f"{p['id']}: conta Cakto desconhecida ({c})")
    if p.get('tipo') in ('produto', 'variante', 'plataforma') and p['servico'] not in srcs:
        erros.append(f"{p['id']}: serviço '{p['servico']}' não está em releases/sources.json")
txt = open(os.path.join(raiz, 'registro', 'produtos.yml'), encoding='utf-8').read()
if re.search(r'(?i)(senha|password|secret|token)\s*:\s*\S{12,}', txt):
    erros.append('parece haver valor de segredo no registro (só nomes e caminhos são permitidos)')
print(f"{len(reg['produtos'])} entradas, {len(hosts)} hosts, {len(srcs)} serviços no mapa de releases")
if erros:
    print('FALHOU:'); [print(' -', e) for e in erros]; sys.exit(1)
print('registro válido')
