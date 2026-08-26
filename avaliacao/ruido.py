# -*- coding: utf-8 -*-
"""Teste de robustez: injeta ruido NOVO, do tipo que o enunciado descreve, e
mede quanto o escore cai.

Todas as operacoes preservam o comprimento do texto, entao os offsets do
gabarito continuam validos e a comparacao e limpa. O ruido segue a garantia do
enunciado: digito nunca vira outro digito - so vira a letra parecida.
"""
import random
import sys

import pandas as pd

from cacador.canon import BaseCanonica
from cacador.pipeline import processa_documento
from .metrica import DEV, HOLDOUT, alinha

DIGITO_PARA_LETRA = {'0': 'O', '1': 'l', '5': 'S', '9': 'g', '6': 'G',
                     '8': 'B', '2': 'Z'}
LETRA_PARA_LETRA = {'e': 'c', 'i': 'l', 'a': 'ã', 'o': '0', 'u': 'ü', 'm': 'rn'}


def suja(texto, taxa, rng):
    """Ruido de OCR preservando comprimento (offsets do gabarito seguem valendo)."""
    saida = list(texto)
    for i, ch in enumerate(texto):
        if rng.random() > taxa:
            continue
        if ch.isdigit():
            # so troca digito por letra se estiver dentro de um run de digitos,
            # e nunca por outro digito
            viz = (i > 0 and texto[i - 1].isdigit()) or (i + 1 < len(texto) and texto[i + 1].isdigit())
            if viz and ch in DIGITO_PARA_LETRA:
                saida[i] = DIGITO_PARA_LETRA[ch]
        elif ch == ' ' and rng.random() < 0.25:
            saida[i] = '\n'                      # quebra de linha no meio
        elif ch.isalpha() and ch.lower() in LETRA_PARA_LETRA:
            sub = LETRA_PARA_LETRA[ch.lower()]
            if len(sub) == 1:
                saida[i] = sub
    return ''.join(saida)


def mede(docs, base, taxa, semente):
    rng = random.Random(semente)
    g = pd.read_csv('dados/goldenset.csv')
    peso_tot = peso_ok = 0.0
    for doc in docs:
        texto = open(f'dados/txt/{doc}.txt', encoding='utf-8').read()
        if taxa:
            texto = suja(texto, taxa, rng)
        gold = [{'inicio': int(r.inicio), 'fim': int(r.fim),
                 'classificacao': r.classificacao, 'nivel': int(r.nivel),
                 'ids': set(str(r.id_canonico).split()) if isinstance(r.id_canonico, str) else set()}
                for r in g[g.documento_id == doc].itertuples()]
        pred = processa_documento(texto, base)['citacoes']
        pares, _ = alinha(gold, pred)
        peso = 1 if gold and gold[0]['nivel'] == 1 else 2
        peso_tot += peso * len(gold)
        for i, j in pares:
            gi, pj = gold[i], pred[j]
            if gi['classificacao'] != pj['classificacao']:
                continue
            if gi['classificacao'] == 'real':
                if str((pj.get('resolucao') or {}).get('id_canonico')) not in gi['ids']:
                    continue
            peso_ok += peso
    return peso_ok / peso_tot


if __name__ == '__main__':
    base = BaseCanonica()
    docs = DEV + HOLDOUT
    print('taxa de ruido | escore (3 sementes)')
    for taxa in (0.0, 0.005, 0.01, 0.02, 0.05, 0.10):
        escores = [mede(docs, base, taxa, s) for s in (1, 2, 3)] if taxa else [mede(docs, base, 0, 0)]
        media = sum(escores) / len(escores)
        print(f'   {taxa:>5.1%}      | {media:6.1%}   ' +
              ('(' + ', '.join(f'{e:.1%}' for e in escores) + ')' if taxa else ''))
