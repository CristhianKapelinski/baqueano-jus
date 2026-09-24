# -*- coding: utf-8 -*-
"""Documento .txt -> JSON do contrato (schema_version 1.2).

O formato segue o exemplo publicado na aba "A tarefa" do site do desafio:
schema_version, documento_id e, por citacao, um id proprio, o span em
codepoints, o trecho literal, tipo, classificacao, resolucao (com `fonte`) e a
confianca opcional.
"""
from .calibracao import CONSTANTE
from .classify import classifica
from .extract import extrai

ESQUEMA = '1.2'
FONTE = 'jusbrasil'


def processa_documento(texto, base, documento_id=None):
    citacoes = []
    for span in extrai(texto):
        classe, id_canonico, _ = classifica(span, base)
        c = {'inicio': span['inicio'], 'fim': span['fim'],
             'trecho': span['trecho'], 'tipo': span['tipo'],
             'classificacao': classe, 'confianca': CONSTANTE,
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
