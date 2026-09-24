# -*- coding: utf-8 -*-
"""Leitura do gabarito, seja ele .xlsx ou .csv.

A organizacao distribuiu o goldenset em planilha e, na versao final do Kaggle,
como `goldenset_offsets.csv`. O conjunto sintetico que geramos sai como
`goldenset.csv`. Um leitor so evita que cada suite decida sozinha.

`id_canonico` e sempre lido como texto: em planilha ele chega como numero e o
pandas o transformaria em float, quebrando a comparacao com o id que o sistema
emite.
"""
import pathlib

import pandas as pd


def caminho(pasta='dados'):
    base = pathlib.Path(pasta)
    for nome in ('goldenset_offsets.csv', 'goldenset.xlsx', 'goldenset.csv'):
        if (base / nome).exists():
            return base / nome
    raise FileNotFoundError(f'nenhum goldenset em {base}')


def carrega(pasta='dados'):
    p = caminho(pasta)
    if p.suffix == '.xlsx':
        g = pd.read_excel(p, dtype={'id_canonico': str})
    else:
        g = pd.read_csv(p, dtype={'id_canonico': str})
    g['id_canonico'] = g['id_canonico'].where(g['id_canonico'].notna(), None)
    return g


def ids_aceitos(linha):
    """Conjunto de ids que contam como acerto para uma citacao do gabarito.

    Desde a atualizacao de 28/08 o campo traz um unico doc_id, porque as
    duplicatas exatas sairam da base. A funcao continua devolvendo conjunto
    para que o codigo nao dependa dessa escolha do organizador.
    """
    v = getattr(linha, 'id_canonico', None)
    return set(str(v).split()) if isinstance(v, str) and v.strip() else set()
