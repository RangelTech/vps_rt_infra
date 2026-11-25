"""Uptime Kuma como código (spec 57 §6.7). Idempotente: cria/atualiza pelo NOME, nunca duplica; recria tudo se o volume se perder.

- administrador: usuário/senha do Infisical (plataforma/uptime-kuma: KUMA_USUARIO, KUMA_SENHA); na primeira vez faz o setup;
- alerta: SÓ e-mail (SMTP da casa, contato@rangeltech.net), um quando cai e outro quando volta;
- monitores: um HTTP por produto e plataforma, a partir do registro único (registro/produtos.yml), e a infraestrutura
  interna (Postgres, pgbouncer, Redis, MinIO) pela rede interna; 60 s, 3 tentativas antes de alertar; aviso de certificado;
- monitores "push" do coletor de saúde (§6.10.5), um por limite crítico;
- página de status interna `rangeltech` agrupada (Produtos, Plataformas, Infraestrutura, Saúde).
Uso: py -3 scripts/kuma/configurar.py
"""
import json
import os
import sys

import yaml
from uptime_kuma_api import MonitorType, NotificationType, UptimeKumaApi

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, '..', '..')
sys.path.insert(0, os.path.join(AQUI, '..', 'infisical'))
from infapi import call, token  # noqa: E402

URL = 'https://uptime.rangeltech.net'
DESTINO_EMAIL = 'lucas.rangel.s.souza@gmail.com'
P = json.load(open(os.path.join(AQUI, '..', 'infisical', 'infisical_projetos.json'), encoding='utf-8'))
TOK = token()


def segredos(projeto, pasta):
    return {s['secretKey']: s['secretValue'] for s in
            call(f"/api/v3/secrets/raw?workspaceId={P[projeto]}&environment=prod&secretPath=/{pasta}", tok=TOK)['secrets']}


def garantir_segredos_kuma():
    try:
        s = segredos('plataforma', 'uptime-kuma')
    except Exception:  # noqa: BLE001
        call('/api/v1/folders', {'workspaceId': P['plataforma'], 'environment': 'prod', 'name': 'uptime-kuma', 'path': '/'}, TOK)
        s = {}
    faltam = [{'secretKey': k, 'secretValue': v} for k, v in (('KUMA_USUARIO', 'lucas'), ('KUMA_SENHA', 'admin@lucas')) if k not in s]
    if faltam:  # decisão do Lucas (§6.7): lucas / admin@lucas, ele troca depois
        call('/api/v3/secrets/batch/raw', {'workspaceId': P['plataforma'], 'environment': 'prod', 'secretPath': '/uptime-kuma', 'secrets': faltam}, TOK)
        s = segredos('plataforma', 'uptime-kuma')
    return s['KUMA_USUARIO'], s['KUMA_SENHA']


def monitores_desejados():
    reg = yaml.safe_load(open(os.path.join(RAIZ, 'registro', 'produtos.yml'), encoding='utf-8'))
    out = []
    for x in reg['produtos']:
        if x['tipo'] == 'produto':
            out.append(('Produtos', x['nome'], MonitorType.HTTP, f"https://{x['hosts'][0]}/health"))
            out.append(('Produtos', x['nome'] + ' (arquivos)', MonitorType.HTTP, f"https://{x['hosts'][0]}/health/arquivos"))
    out += [
        ('Plataformas', 'Segundo Cérebro: site', MonitorType.HTTP, 'https://segundocerebro.pro/'),
        ('Plataformas', 'Segundo Cérebro: app web', MonitorType.HTTP, 'https://app.segundocerebro.pro/'),
        ('Plataformas', 'Segundo Cérebro: remoto', MonitorType.HTTP, 'https://remoto.rangeltech.net/'),
        ('Plataformas', 'Qwen: llm-access', MonitorType.HTTP, 'https://qwen.rangeltech.net/health'),
        ('Plataformas', 'Qwen: API', MonitorType.HTTP, 'https://api.segundocerebro.pro/health'),
        ('Plataformas', 'LUAR', MonitorType.HTTP, 'https://luar.rangeltech.net/'),
        ('Plataformas', 'Mentoria (site)', MonitorType.HTTP, 'https://ai.rangeltech.net/'),
        ('Infraestrutura', 'Infisical', MonitorType.HTTP, 'https://infisical.rangeltech.net/api/status'),
        ('Infraestrutura', 'MinIO (vivo)', MonitorType.HTTP, 'http://minio:9000/minio/health/live'),
        ('Infraestrutura', 'MinIO (pronto)', MonitorType.HTTP, 'http://minio:9000/minio/health/ready'),
        ('Infraestrutura', 'Postgres', MonitorType.PORT, 'postgres:5432'),
        ('Infraestrutura', 'pgbouncer', MonitorType.PORT, 'pgbouncer:5432'),
        ('Infraestrutura', 'Redis', MonitorType.PORT, 'redis:6379'),
    ]
    for nome in ('disco', 'postgres-conexoes', 'postgres-cache', 'postgres-transacao-longa',
                 'minio-pronto', 'minio-erros', 'backup-idade', 'coletor'):
        out.append(('Saúde', f'Saúde: {nome}', MonitorType.PUSH, nome))
    return out


def main():
    usuario, senha = garantir_segredos_kuma()
    api = UptimeKumaApi(URL, timeout=180)
    if api.need_setup():
        api.setup(usuario, senha)
        print('administrador criado:', usuario)
    api.login(usuario, senha)

    smtp = segredos('rt-produtos', 'astralai')
    notif = {'name': 'E-mail do Lucas', 'type': NotificationType.SMTP, 'isDefault': True, 'applyExisting': True,
             'smtpHost': smtp['SMTP_HOST'], 'smtpPort': int(smtp['SMTP_PORT']), 'smtpSecure': False,
             'smtpUsername': smtp['SMTP_USER'], 'smtpPassword': smtp['SMTP_PASSWORD'],
             'smtpFrom': f"Monitor Rangel Tech <{smtp['SMTP_USER']}>", 'smtpTo': DESTINO_EMAIL,
             'smtpBCC': smtp['SMTP_USER']}  # cópia na caixa da casa: o QA confere a chegada por IMAP
    atuais = {n['name']: n for n in api.get_notifications()}
    if notif['name'] in atuais:
        api.edit_notification(atuais[notif['name']]['id'], **notif)
    else:
        api.add_notification(**notif)
    nid = {n['name']: n['id'] for n in api.get_notifications()}[notif['name']]

    existentes = {m['name']: m for m in api.get_monitors()}
    grupos, pushes = {}, {}
    for grupo, nome, tipo, alvo in monitores_desejados():
        base = {'type': tipo, 'name': nome, 'interval': 60, 'retryInterval': 60, 'maxretries': 3, 'notificationIDList': [nid]}
        if tipo == MonitorType.HTTP:
            base.update(url=alvo, expiryNotification=alvo.startswith('https'), accepted_statuscodes=['200-299'])
        elif tipo == MonitorType.PORT:
            h, porta = alvo.split(':')
            base.update(hostname=h, port=int(porta))
        elif tipo == MonitorType.PUSH:
            base.update(interval=600, maxretries=0)  # 10 min sem sinal do coletor = alerta
        if nome in existentes:
            e = existentes[nome]
            mudou = any(str(e.get(k)) != str(v) for k, v in base.items() if k in ('url', 'hostname', 'port', 'interval', 'maxretries'))
            if mudou:  # só edita o que mudou (editar reinicia o monitor e é lento no Kuma)
                api.edit_monitor(e['id'], **{k: v for k, v in base.items() if k != 'type'})
            mid = e['id']
        else:
            mid = api.add_monitor(**base)['monitorID']
        grupos.setdefault(grupo, []).append({'id': mid})
        if tipo == MonitorType.PUSH:
            tk = (existentes.get(nome) or {}).get('pushToken') or api.get_monitor(mid).get('pushToken')
            if not tk:  # a API do Kuma não gera o token (a tela gera); criamos uma vez e nunca trocamos
                import secrets as _s
                tk = _s.token_urlsafe(24).replace('-', 'x').replace('_', 'y')[:30]
                api.edit_monitor(mid, pushToken=tk)
            pushes[alvo] = tk

    slug = 'rangeltech'
    if slug not in {s['slug'] for s in api.get_status_pages()}:
        api.add_status_page(slug, 'Rangel Tech')
    api.save_status_page(slug, title='Rangel Tech', description='Monitoramento interno (spec 57 §6.7)',
                         publicGroupList=[{'name': g, 'monitorList': ms} for g, ms in grupos.items()])
    api.disconnect()
    print(f'{sum(len(v) for v in grupos.values())} monitores em {len(grupos)} grupos; e-mail para {DESTINO_EMAIL}; página /status/{slug}')
    # tokens dos monitores push do coletor vão para o Infisical (o coletor lê no deploy)
    atual = segredos('plataforma', 'uptime-kuma')
    novos = [{'secretKey': 'KUMA_PUSH_' + k.upper().replace('-', '_'), 'secretValue': v} for k, v in pushes.items()
             if 'KUMA_PUSH_' + k.upper().replace('-', '_') not in atual]
    if novos:
        call('/api/v3/secrets/batch/raw', {'workspaceId': P['plataforma'], 'environment': 'prod', 'secretPath': '/uptime-kuma', 'secrets': novos}, TOK)
    print('tokens push no Infisical:', len(pushes))


if __name__ == '__main__':
    main()
