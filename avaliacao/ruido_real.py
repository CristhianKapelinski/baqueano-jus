# -*- coding: utf-8 -*-
"""Mede a taxa de corrupcao real dos documentos de nivel 2.

    python -m avaliacao.ruido_real

Nao existe original limpo para comparar documento a documento, mas as frases de
enchimento do gerador aparecem nos dois niveis. Parear cada frase do nivel 2 com
sua versao do nivel 1 e contar os caracteres que diferem da a taxa medida.

Duas mascaras sao obrigatorias antes de comparar, e sem elas o numero sai
inflado por um fator de cinco:

* as CITACOES, porque frases que diferem por conterem citacoes diferentes medem
  o sorteio do gerador e nao o ruido;
* os DIGITOS, porque numero de folha, data e valor tambem sao sorteados.
"""
import difflib
import re

import pandas as pd

LIMIAR = 0.88          # similaridade minima para considerar duas frases a mesma
MIN, MAX = 40, 170     # tamanho de frase que vale comparar


def _preparado(doc, gabarito):
    texto = open(f'dados/txt/{doc}.txt', encoding='utf-8').read()
    for r in sorted(gabarito[gabarito.documento_id == doc].itertuples(),
                    key=lambda r: -int(r.inicio)):
        texto = texto[:int(r.inicio)] + '«C»' + texto[int(r.fim):]
    return re.sub(r'\s+', ' ', re.sub(r'\d', '#', texto))


def _frases(nivel, gabarito):
    saida = []
    for doc in sorted(set(gabarito[gabarito.nivel == nivel].documento_id)):
        saida += [f.strip() for f in re.split(r'(?<=[.])\s+', _preparado(doc, gabarito))
                  if MIN < len(f) < MAX and '«C»' not in f]
    return saida


def mede():
    g = pd.read_csv('dados/goldenset.csv')
    limpas = list(dict.fromkeys(_frases(1, g)))
    caracteres = diferentes = pares = 0
    for suja in _frases(2, g):
        perto = difflib.get_close_matches(suja, limpas, n=1, cutoff=LIMIAR)
        if not perto:
            continue
        ops = difflib.SequenceMatcher(None, perto[0], suja).get_opcodes()
        diferentes += sum(max(i2 - i1, j2 - j1) for op, i1, i2, j1, j2 in ops if op != 'equal')
        caracteres += len(suja)
        pares += 1
    return pares, caracteres, diferentes


if __name__ == '__main__':
    pares, caracteres, diferentes = mede()
    print(f'frases pareadas          : {pares}')
    print(f'caracteres comparados    : {caracteres}')
    print(f'caracteres corrompidos   : {diferentes}')
    print(f'taxa medida no nivel 2   : {diferentes / caracteres:.2%}')
