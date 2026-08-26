# -*- coding: utf-8 -*-
"""Documento .txt -> JSON do Contrato de Entrada e Saida."""
from .classify import classifica
from .extract import extrai
from .features import sigmoide, vetor

try:
    from .calibracao import PESOS
except ImportError:  # ainda nao rodou calibra.py
    PESOS = None


def processa_documento(texto, base, documento_id=None):
    citacoes = []
    for span in extrai(texto):
        classe, id_canonico, conf, diag = classifica(span, base)
        if PESOS:
            conf = sigmoide(sum(p * x for p, x in zip(PESOS, vetor(span, classe, diag))))
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
