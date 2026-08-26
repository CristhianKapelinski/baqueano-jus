# -*- coding: utf-8 -*-
"""Documento .txt -> JSON do Contrato de Entrada e Saida."""
from .classify import classifica
from .extract import extrai

try:
    from .calibracao import CONFIANCA, PADRAO
except ImportError:  # ainda nao rodou calibra.py
    CONFIANCA, PADRAO = {}, None


def processa_documento(texto, base, documento_id=None):
    citacoes = []
    for span in extrai(texto):
        classe, id_canonico, conf = classifica(span, base)
        # a confianca empirica, quando existe, vale mais que a heuristica
        conf = CONFIANCA.get((span['forma'], classe), conf if PADRAO is None else conf)
        c = {'inicio': span['inicio'], 'fim': span['fim'],
             'trecho': span['trecho'], 'tipo': span['tipo'],
             'classificacao': classe, 'confianca': round(conf, 4),
             'resolucao': {'id_canonico': id_canonico} if id_canonico else None,
             # 'forma' e diagnostico interno; run.py corta antes de escrever o JSON
             'forma': span['forma']}
        citacoes.append(c)
    saida = {'citacoes': citacoes}
    if documento_id:
        saida['documento_id'] = documento_id
    return saida
