# -*- coding: utf-8 -*-
"""Decide, por medicao, como emitir `confianca` - e grava a decisao.

O bonus vale ate 10% e e medido por Brier score. Este script compara as
estrategias possiveis por validacao cruzada agrupada por DOCUMENTO sobre o
goldenset (o unico dado real), e escreve a vencedora em cacador/calibracao.py.
"""
import argparse
import collections

import numpy as np

from avaliacao.amostragem import amostras, auc, brier, ece, treina
from cacador.canon import BaseCanonica
from cacador.features import CLASSES, FORMAS, NOMES


def cv_taxa(chaves, y, grupos, acc, alfa=2.0, folds=6):
    docs = np.unique(grupos)
    np.random.default_rng(0).shuffle(docs)
    p = np.zeros(len(y))
    for f in np.array_split(docs, folds):
        te = np.isin(grupos, f)
        soma, n = collections.Counter(), collections.Counter()
        for k, alvo in zip(chaves[~te], y[~te]):
            soma[k] += alvo
            n[k] += 1
        for i in np.where(te)[0]:
            k = chaves[i]
            p[i] = (soma[k] + alfa * acc) / (n[k] + alfa)
    return p


def cv_logistica(X, y, grupos, folds=6):
    docs = np.unique(grupos)
    np.random.default_rng(0).shuffle(docs)
    p = np.zeros(len(y))
    for f in np.array_split(docs, folds):
        te = np.isin(grupos, f)
        w = treina(X[~te], y[~te], l2=1.0, alvo='logloss')
        p[te] = 1 / (1 + np.exp(-np.clip(X[te] @ w, -30, 30)))
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--margem', type=float, default=0.01,
                    help='quanto abaixo da acuracia medida emitir a constante, '
                         'para nao ficar superconfiante no conjunto cego')
    a = ap.parse_args()
    base = BaseCanonica()
    X, y, grupos = amostras(base, 'dados/txt', 'dados/goldenset.csv')
    acc = y.mean()
    iF = [NOMES.index(f'forma={f}') for f in FORMAS]
    iC = [NOMES.index(f'classe={c}') for c in CLASSES]
    forma = np.array([FORMAS[int(np.argmax(x[iF]))] for x in X])
    classe = np.array([CLASSES[int(np.argmax(x[iC]))] for x in X])

    print(f'dado real: {len(y)} predicoes, {int((1 - y).sum())} erradas, '
          f'acerto {acc:.4f}\n')
    cand = {
        'constante': np.full(len(y), acc),
        'taxa por forma': cv_taxa(forma, y, grupos, acc),
        'taxa por classe': cv_taxa(classe, y, grupos, acc),
        'taxa por forma+classe': cv_taxa(
            np.array([f'{f}|{c}' for f, c in zip(forma, classe)]), y, grupos, acc),
        'regressao logistica': cv_logistica(X, y, grupos),
    }
    print(f'{"estrategia":26s} {"Brier":>9s} {"ECE":>9s} {"AUC":>7s} {"vs constante":>14s}')
    ref = brier(cand['constante'], y)
    for nome, p in cand.items():
        print(f'{nome:26s} {brier(p, y):9.5f} {ece(p, y):9.5f} {auc(p, y):7.3f} '
              f'{ref - brier(p, y):+14.5f}')
    melhor = min(cand, key=lambda k: brier(cand[k], y))
    print(f'\n-> vence: {melhor}')

    if melhor != 'constante':
        raise SystemExit(
            'Um modelo passou a bater a constante - reveja escolhe_confianca.py '
            'para gravar os pesos em vez do valor fixo.')
    valor = round(float(acc) - a.margem, 4)
    corpo = ('# -*- coding: utf-8 -*-\n'
             '"""Gerado por escolhe_confianca.py - NAO editar a mao.\n\n'
             'Nenhum modelo bateu uma constante no dado real: com poucos erros\n'
             'no goldenset nao ha sinal para ajustar nada mais fino. Emitimos a\n'
             'acuracia medida, com uma margem para baixo - errar por excesso de\n'
             'confianca custa mais no Brier do que errar por falta.\n'
             '"""\n\n'
             'MODO = "constante"\n'
             f'CONSTANTE = {valor}\n'
             f'# acuracia medida no goldenset: {acc:.4f}; margem aplicada: {a.margem}\n'
             'PESOS = None\n')
    open('cacador/calibracao.py', 'w', encoding='utf-8').write(corpo)
    print(f'cacador/calibracao.py: constante {valor} '
          f'(acuracia {acc:.4f} menos margem {a.margem})')


if __name__ == '__main__':
    main()
