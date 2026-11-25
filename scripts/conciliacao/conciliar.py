#!/usr/bin/env python3
"""Conciliação diária da Cakto (spec 57, §10A.2). Compara os pedidos e assinaturas das DUAS contas Cakto (Lucas e Adriano)
com o que cada produto liberou (SQLite de cada produto hoje; banco `produtos` depois da migração) e com o Segundo Cérebro
(`llm_access`). Só LÊ: nunca altera o que a Cakto cobra nem o que o produto liberou. Gera um relatório e avisa por e-mail
quando há divergência.

Uso (na VPS, como root):  conciliar.py [--sem-email] [--saida /caminho/relatorio.json]
Credenciais: Infisical (identidade de leitura em /opt/platform/secrets/infisical-leitura.env): plataforma/cakto-lucas,
plataforma/cakto-adriano e qwen/llm-access (SMTP).
"""
from __future__ import annotations
import glob, json, os, re, smtplib, sqlite3, subprocess, sys, time, unicodedata, urllib.request
from email.message import EmailMessage

AQUI = os.path.dirname(os.path.abspath(__file__))
UA = {'User-Agent': 'curl/8.5.0'}

# nome do produto na Cakto (prefixo) -> pasta de dados do produto (container) ; Segundo Cérebro é tratado à parte
PREFIXOS = [
    ('maquina virtual segundo cerebro', 'segundo-cerebro'), ('segundo cerebro', 'segundo-cerebro'),
    ('viralizai', 'viralizai'), ('cortai', 'cortai'), ('rendai', 'rendai'), ('perfilai', 'perfilai'),
    ('insta ai', 'perfilai'), ('face ai', 'perfilai'), ('tittok ai', 'perfilai'), ('tiktok ai', 'perfilai'), ('linkdn ai', 'perfilai'),
    ('anima ai', 'animaai'), ('posta ai', 'postaai'), ('atende ai', 'atendeai'), ('astral ai', 'astralai'),
    ('shape ai', 'shapeai'), ('casa ai', 'casaai'), ('arena bruta', 'arenabruta'), ('boate azul', 'boateazul'),
    ('mentoria', 'mentoria'), ('area do aluno', 'mentoria'),
]
PAGO = {'paid', 'approved', 'authorized', 'active', 'completed'}
DEVOLVIDO = {'refunded', 'chargedback', 'chargeback', 'canceled', 'cancelled', 'refused'}


def sem_acento(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s or '') if unicodedata.category(c) != 'Mn').lower()


def produto_de(nome_cakto: str) -> str | None:
    n = sem_acento(nome_cakto)
    for pre, alvo in PREFIXOS:
        if n.startswith(pre):
            return alvo
    return None


# ------------------------------------------------------------------ Infisical e Cakto
def infisical(projeto: str, pasta: str, arq='/opt/platform/secrets/infisical-leitura.env') -> dict:
    cfg = dict(l.strip().split('=', 1) for l in open(arq, encoding='utf-8') if '=' in l and not l.startswith('#'))
    proj = json.load(open(os.path.join(AQUI, '..', 'infisical', 'infisical_projetos.json')))
    def call(path, body=None, tok=None):
        h = dict(UA, **{'Content-Type': 'application/json'}, **({'Authorization': 'Bearer ' + tok} if tok else {}))
        r = urllib.request.Request(cfg['INFISICAL_URL'] + path, data=json.dumps(body).encode() if body else None, headers=h)
        return json.load(urllib.request.urlopen(r, timeout=30))
    tok = call('/api/v1/auth/universal-auth/login', {'clientId': cfg['INFISICAL_CLIENT_ID'], 'clientSecret': cfg['INFISICAL_CLIENT_SECRET']})['accessToken']
    sec = call(f'/api/v3/secrets/raw?workspaceId={proj[projeto]}&environment=prod&secretPath=/{pasta}', tok=tok)['secrets']
    return {s['secretKey']: s['secretValue'] for s in sec}


def cakto_listar(cred: dict, recurso: str) -> list:
    body = f"client_id={cred['CAKTO_CLIENT_ID']}&client_secret={cred['CAKTO_CLIENT_SECRET']}".encode()
    tok = json.load(urllib.request.urlopen(urllib.request.Request('https://api.cakto.com.br/public_api/token/', data=body,
                    headers=dict(UA, **{'Content-Type': 'application/x-www-form-urlencoded'})), timeout=30))['access_token']
    itens, url = [], f'https://api.cakto.com.br/public_api/{recurso}/?limit=50'
    while url:
        for tentativa in range(4):                    # a API as vezes corta a resposta no meio (IncompleteRead): tenta de novo
            try:
                d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=dict(UA, Authorization='Bearer ' + tok)), timeout=60))
                break
            except Exception:
                if tentativa == 3:
                    raise
                time.sleep(3 * (tentativa + 1))
        itens += d.get('results', []) if isinstance(d, dict) else d
        url = d.get('next') if isinstance(d, dict) else None
    return itens


# ------------------------------------------------------------------ o que cada produto liberou
def liberacoes_produtos(base='/opt/platform/data') -> dict:
    """{produto: {'eventos': set(id_pedido), 'ativos': {email: pedido}}} lendo os SQLite em modo somente leitura."""
    out, agora = {}, time.time()
    for d in sorted(glob.glob(base + '/*/')):
        n = os.path.basename(d.rstrip('/'))
        dbs = glob.glob(d + '*.db')
        if not dbs:
            continue
        c = sqlite3.connect('file:' + dbs[0] + '?mode=ro', uri=True)
        t = {r[0] for r in c.execute("select name from sqlite_master where type='table'")}
        if 'usuarios' not in t:
            continue
        ev = {str(r[0]).split(':')[0] for r in c.execute('select id from eventos_cakto')} if 'eventos_cakto' in t else set()
        ativos = {}
        for email, pedido, ate in c.execute('select email, pedido, ativo_ate from usuarios'):
            if ate and ate > agora:
                ativos[(email or '').lower()] = pedido
        if 'assinaturas' in t:
            for email, pedido, ate in c.execute('select u.email, a.pedido, a.ativo_ate from assinaturas a join usuarios u on u.id=a.usuario'):
                if ate and ate > agora:
                    ativos[(email or '').lower()] = pedido
        out[n] = {'eventos': ev, 'ativos': ativos}
    return out


def liberacoes_cerebro() -> dict:
    sql = ("select a.email, s.external_id, s.status from access.subscriptions s join access.accounts a on a.id=s.account_id "
           "where s.provider='cakto'")
    r = subprocess.run(['docker', 'exec', 'postgres', 'psql', '-U', 'platform_admin', '-d', 'llm_access', '-At', '-F', '|', '-c', sql],
                       capture_output=True, text=True, encoding='utf-8', timeout=60)
    ativos, eventos = {}, set()
    for l in r.stdout.splitlines():
        email, ext, st = (l.split('|') + ['', '', ''])[:3]
        if ext:
            eventos.add(ext)
        if st in ('active', 'late'):
            ativos[email.lower()] = ext
    return {'eventos': eventos, 'ativos': ativos}


# ------------------------------------------------------------------ comparação (pura, testável)
def conciliar(pedidos_por_conta: dict, liberado: dict) -> list:
    """pedidos_por_conta: {conta: [pedido Cakto]}; liberado: {produto: {'eventos', 'ativos'}}. Devolve divergências."""
    div, pagos_por_email = [], {}
    for conta, pedidos in pedidos_por_conta.items():
        for p in pedidos:
            if p.get('_tipo') == 'assinatura':
                continue                                  # assinatura so entra como "id conhecido pela Cakto" (abaixo)
            if not isinstance(p.get('product'), dict):
                continue
            nome = ((p.get('product') or {}).get('name')) or p.get('product_name') or ''
            prod = produto_de(nome)
            pid = str(p.get('id') or p.get('refId') or '')
            email = ((p.get('customer') or {}).get('email') or '').lower()
            st = str(p.get('status') or '').lower()
            if prod is None:
                if conta == 'adriano':
                    continue                              # a conta do Adriano vende outros produtos dele: so o Cerebro e o Viralizai sao nossos
                div.append({'tipo': 'pedido sem produto cadastrado', 'conta': conta, 'pedido': pid, 'produto_cakto': nome, 'email': email})
                continue
            lib = liberado.get(prod)
            if lib is None:
                continue                                  # produto sem base para comparar (ex.: mentoria, conferida no proprio sistema)
            if st in PAGO:
                pagos_por_email.setdefault((prod, email), []).append(pid)
                if pid not in lib['eventos'] and email not in lib['ativos']:
                    div.append({'tipo': 'pagou e não liberou', 'conta': conta, 'pedido': pid, 'produto': prod, 'email': email})
            elif st in DEVOLVIDO and email in lib['ativos'] and lib['ativos'][email] == pid:
                div.append({'tipo': 'reembolso/cancelamento e continua ativo', 'conta': conta, 'pedido': pid, 'produto': prod, 'email': email})
    todos_ids = set()
    for ps in pedidos_por_conta.values():
        for p in ps:
            for campo in ('id', 'refId', 'subscription', 'subscription_id', 'parent_order'):
                v = p.get(campo)
                if isinstance(v, dict):
                    v = v.get('id')
                if v:
                    todos_ids.add(str(v))
            for o in p.get('orders') or []:
                todos_ids.add(str(o.get('id') if isinstance(o, dict) else o))
    for prod, lib in liberado.items():
        for email, ped in lib['ativos'].items():
            # cortesia/teste (sem pedido) nao e divergencia; pedido que a Cakto nao conhece em nenhuma das contas, e
            if ped and str(ped) not in todos_ids and not str(ped).startswith('qa-'):   # 'qa-...': compra simulada dos testes de QA
                div.append({'tipo': 'liberado sem pagamento na Cakto', 'produto': prod, 'email': email, 'pedido': ped})
    return div


def avisar(divs: list, smtp: dict) -> None:
    m = EmailMessage()
    m['From'], m['To'] = smtp.get('SMTP_FROM', 'contato@rangeltech.net'), 'lucas.rangel@outlook.com'
    m['Subject'] = f'Conciliação Cakto: {len(divs)} divergência(s)'
    m.set_content('Divergências entre a Cakto e o que os produtos liberaram:\n\n' + '\n'.join(json.dumps(d, ensure_ascii=False) for d in divs))
    with smtplib.SMTP(smtp['SMTP_HOST'], int(smtp.get('SMTP_PORT', '587')), timeout=30) as s:
        s.starttls()
        if smtp.get('SMTP_USER'):
            s.login(smtp['SMTP_USER'], smtp.get('SMTP_PASSWORD', ''))
        s.send_message(m)


def main() -> int:
    sem_email = '--sem-email' in sys.argv
    saida = sys.argv[sys.argv.index('--saida') + 1] if '--saida' in sys.argv else '/opt/platform/data/conciliacao/ultimo.json'
    pedidos = {}
    base = os.path.dirname(saida)
    os.makedirs(base, exist_ok=True)
    for conta in ('lucas', 'adriano'):
        cache = os.path.join(base, f'cakto-{conta}.json')
        if '--cache' in sys.argv and os.path.exists(cache):
            pedidos[conta] = json.load(open(cache, encoding='utf-8'))
            continue
        cred = infisical('plataforma', 'cakto-' + conta)
        pedidos[conta] = cakto_listar(cred, 'orders') + [dict(s, _tipo='assinatura') for s in cakto_listar(cred, 'subscriptions')]
        json.dump(pedidos[conta], open(cache, 'w', encoding='utf-8'))
    liberado = liberacoes_produtos()
    liberado['segundo-cerebro'] = liberacoes_cerebro()
    divs = conciliar(pedidos, liberado)
    rel = {'quando': time.strftime('%Y-%m-%d %H:%M:%S'), 'pedidos': {c: len(v) for c, v in pedidos.items()},
           'produtos_lidos': sorted(liberado), 'divergencias': divs}
    os.makedirs(os.path.dirname(saida), exist_ok=True)
    json.dump(rel, open(saida, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in rel.items() if k != 'divergencias'}, ensure_ascii=False), '| divergências:', len(divs))
    if divs and not sem_email:
        avisar(divs, infisical('qwen', 'llm-access'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
