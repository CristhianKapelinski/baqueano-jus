# -*- coding: utf-8 -*-
"""Documento .txt -> JSON do contrato (schema_version 1.2).

O formato segue o exemplo publicado na aba "A tarefa" do site do desafio:
schema_version, documento_id e, por citacao, um id proprio, o span em
codepoints, o trecho literal, tipo, classificacao, resolucao (com `fonte`) e a
confianca opcional.
"""
from .classify import classifica
from .extract import extrai
from .features import sigmoide, vetor

ESQUEMA = '1.2'
FONTE = 'jusbrasil'

try:
    from .calibracao import CONSTANTE, MODO, PESOS
except ImportError:  # ainda nao rodou escolhe_confianca.py
    MODO, CONSTANTE, PESOS = None, None, None


def processa_documento(texto, base, documento_id=None):
    citacoes = []
    for span in extrai(texto):
        classe, id_canonico, conf, diag = classifica(span, base)
        if MODO == 'constante':
            conf = CONSTANTE
        elif PESOS:
            conf = sigmoide(sum(p * x for p, x in zip(PESOS, vetor(span, classe, diag))))
        c = {'inicio': span['inicio'], 'fim': span['fim'],
             'trecho': span['trecho'], 'tipo': span['tipo'],
             'classificacao': classe, 'confianca': round(conf, 4),
             'resolucao': ({'fonte': FONTE, 'id_canonico': id_canonico}
                           if id_canonico else None),
             # 'forma' e diagnostico interno; run.py corta antes de escrever o JSON
             'forma': span['forma']}
        citacoes.append(c)
    for i, c in enumerate(citacoes, 1):
        c['id'] = f'c{i}'
    saida = {'schema_version': ESQUEMA, 'citacoes': citacoes}
    if documento_id:
        saida = {'schema_version': ESQUEMA, 'documento_id': documento_id,
                 'citacoes': citacoes}
    return saida
