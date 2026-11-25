"""Testes da conciliação com dados simulados (cada tipo de divergência forçado de propósito). Rodar: python3 teste_conciliar.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conciliar import conciliar, produto_de

assert produto_de('Cortaí Pro - Mensal') == 'cortai'
assert produto_de('Posta AI Insta Top - Mensal') == 'postaai'
assert produto_de('TitTok AI Start - Mensal') == 'perfilai'
assert produto_de('Segundo Cérebro Lite') == 'segundo-cerebro'
assert produto_de('Máquina virtual Segundo Cérebro') == 'segundo-cerebro'
assert produto_de('GRUPO VIP FECHADO') is None

pedidos = {
    'lucas': [
        {'id': 'p1', 'status': 'paid', 'product': {'name': 'Cortaí Pro - Mensal'}, 'customer': {'email': 'ok@x.com'}},       # tudo certo
        {'id': 'p2', 'status': 'paid', 'product': {'name': 'Rendaí Start - Mensal'}, 'customer': {'email': 'nao@x.com'}},    # pagou e não liberou
        {'id': 'p3', 'status': 'refunded', 'product': {'name': 'Cortaí Start - Mensal'}, 'customer': {'email': 'dev@x.com'}},# reembolso e ativo
        {'id': 'p4', 'status': 'paid', 'product': {'name': 'Produto Estranho'}, 'customer': {'email': 'z@x.com'}},          # sem produto
    ],
    'adriano': [
        {'id': 'p5', 'status': 'paid', 'product': {'name': 'Viralizaí Corte - Mensal'}, 'customer': {'email': 'fael@x.com'}},# certo (conta do Fael)
        {'id': 'p6', 'status': 'paid', 'product': {'name': 'GRUPO VIP FECHADO'}, 'customer': {'email': 'a@x.com'}},           # produto do Adriano: ignorar
    ],
}
liberado = {
    'cortai': {'eventos': {'p1', 'p3', 'p9'}, 'ativos': {'ok@x.com': 'p1', 'dev@x.com': 'p3', 'gratis@x.com': 'p9'}},  # p9: liberado sem pagamento
    'rendai': {'eventos': set(), 'ativos': {}},
    'viralizai': {'eventos': {'p5'}, 'ativos': {'fael@x.com': 'p5'}},
}
d = conciliar(pedidos, liberado)
tipos = sorted(x['tipo'] for x in d)
esperado = sorted(['pagou e não liberou', 'reembolso/cancelamento e continua ativo', 'pedido sem produto cadastrado', 'liberado sem pagamento na Cakto'])
assert tipos == esperado, tipos
assert not conciliar({'lucas': [], 'adriano': []}, {'cortai': {'eventos': set(), 'ativos': {'cortesia@x.com': None}}}), 'cortesia (sem pedido) nao e divergencia'
print('teste_conciliar: OK (4 tipos de divergência achados; cortesia e pedido certo ignorados)')
