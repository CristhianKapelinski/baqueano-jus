# -*- coding: utf-8 -*-
"""Decide, por medicao, como emitir `confianca` - e grava a decisao.

O bonus vale ate 10% e e medido por Brier score, em que zero e perfeito. O
script compara as estrategias sobre o goldenset, que e o unico dado real, e
grava a vencedora em baqueano/calibracao.py.

Duas escolhas de desenho importam para a conclusao ser honesta:

* A validacao cruzada e agrupada por DOCUMENTO, nunca por citacao, para nao
  vazar contexto de um documento para ele mesmo.
* A vencedora so desbanca a constante se a vantagem sobreviver a um bootstrap
  por documento. Com 228 predicoes e 7 erros, diferencas de milesimo no Brier
  cabem inteiras dentro do ruido de amostragem, e escolher pela media seria
  escolher pelo acaso.

Entre as candidatas esta o modelo treinado no conjunto sintetico, onde os erros
sao mais numerosos, e recentrado na taxa de acerto real. E a unica forma de dar
ao ajuste mais erros do que o goldenset oferece.
"""
import argparse
import collections

import numpy as np

import numpy as np

from avaliacao.amostragem import amostras, auc, brier, ece, treina
from baqueano.canon import BaseCanonica
from baqueano.features import CLASSES, FORMAS, NOMES


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


def _do_sintetico(base, Xg, acc, pastas=('sintetico', 'sintetico_dificil')):
    """Modelo ajustado onde ha erro em quantidade, recentrado na taxa real."""
    Xs, ys = [], []
    for pasta in pastas:
        try:
            X, y, _ = amostras(base, f'{pasta}/txt', f'{pasta}/goldenset.csv', id_str=True)
        except FileNotFoundError:
            continue
        if (1 - y).sum():          # sem erro nenhum nao ha o que aprender
            Xs.append(X); ys.append(y)
    if not Xs:
        return np.full(len(Xg), acc)
    w = treina(np.vstack(Xs), np.concatenate(ys), l2=1.0)
    z = Xg @ w
    z = z - z.mean() + np.log(acc / (1 - acc))
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def _bootstrap(referencia, candidato, y, grupos, reamostras=4000, semente=0):
    """IC da vantagem do candidato sobre a referencia, reamostrando DOCUMENTOS.

    O documento e a unidade de amostragem: citacoes do mesmo documento nao sao
    independentes, e reamostrar citacao a citacao estreitaria o intervalo de
    mentira.
    """
    docs = np.unique(grupos)
    indices = {d: np.where(grupos == d)[0] for d in docs}
    rng = np.random.default_rng(semente)
    difs = np.empty(reamostras)
    for k in range(reamostras):
        idx = np.concatenate([indices[d] for d in rng.choice(docs, len(docs), replace=True)])
        difs[k] = brier(referencia[idx], y[idx]) - brier(candidato[idx], y[idx])
    lo, hi = np.percentile(difs, [2.5, 97.5])
    return lo, hi, float((difs > 0).mean())


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
        'sintetico, recentrado': _do_sintetico(base, X, acc),
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
    # o bootstrap compara sempre a MELHOR ajustada contra a constante: e a
    # unica comparacao que decide alguma coisa.
    ajustadas = {k: v for k, v in cand.items() if k != 'constante'}
    desafiante = min(ajustadas, key=lambda k: brier(ajustadas[k], y))
    lo, hi, vitorias = _bootstrap(cand['constante'], ajustadas[desafiante], y, grupos)
    print(f'\nmelhor ajustada: {desafiante}')
    print(f'vantagem sobre a constante: {brier(cand["constante"], y) - brier(ajustadas[desafiante], y):+.5f}'
          f'  IC 95% [{lo:+.5f}, {hi:+.5f}]  vence em {vitorias:.0%} das reamostras')
    melhor = desafiante if lo > 0 else 'constante'
    print(f'-> {"vence " + desafiante if lo > 0 else "a vantagem nao sobrevive ao ruido; fica a constante"}')

    if melhor != 'constante':
        raise SystemExit(
            'Um modelo passou a bater a constante com folga - grave os pesos '
            'em vez do valor fixo.')
    valor = round(float(acc) - a.margem, 4)
    corpo = ('# -*- coding: utf-8 -*-\n'
             '"""Gerado por escolhe_confianca.py - NAO editar a mao.\n\n'
             'Nenhuma estrategia ajustada superou uma constante COM FOLGA neste\n'
             'conjunto. Isso nao diz que nao existe sinal: diz que 228 predicoes\n'
             'com 7 erros nao tem resolucao para separar uma vantagem de\n'
             'milesimo do ruido de amostragem. Ate haver mais dado real\n'
             'rotulado, a constante e a escolha defensavel. Emitimos a acuracia\n'
             'medida com uma margem para baixo, porque errar por excesso de\n'
             'confianca custa mais no Brier do que errar por falta.\n'
             '"""\n\n'
             'MODO = "constante"\n'
             f'CONSTANTE = {valor}\n'
             f'# acuracia medida no goldenset: {acc:.4f}; margem aplicada: {a.margem}\n'
             'PESOS = None\n')
    open('baqueano/calibracao.py', 'w', encoding='utf-8').write(corpo)
    print(f'baqueano/calibracao.py: constante {valor} '
          f'(acuracia {acc:.4f} menos margem {a.margem})')


if __name__ == '__main__':
    main()
