# -*- coding: utf-8 -*-
"""Treina o modelo de confianca e escreve cacador/calibracao.py.

A metrica do desafio da ate 10% de bonus para quem manda `confianca` bem
ajustada: a probabilidade de que a classe - e o link, nas `real` - esteja certa.
Uma constante nao ganha esse bonus; uma tabela grosseira ganha pouco.

Aqui a confianca vem de uma regressao logistica sobre features do proprio
processo de decisao (quantos feitos casaram, se a pista de tribunal confirmou,
formato do numero, ruido de OCR no span). O treino usa o goldenset MAIS o
conjunto sintetico - ~3.000 exemplos em vez de 225 -, e a avaliacao e por
validacao cruzada agrupada por DOCUMENTO, nunca por citacao, para nao vazar
contexto de um documento para ele mesmo.
"""
import argparse
import collections
import glob

import numpy as np
import pandas as pd

from cacador.canon import BaseCanonica
from cacador.classify import classifica
from cacador.extract import extrai
from cacador.features import NOMES, vetor
from eval import alinha


def amostras(base, dir_txt, csv, id_str=False):
    g = pd.read_csv(csv, dtype={'id_canonico': str} if id_str else None)
    X, y, grupos = [], [], []
    for doc in sorted(set(g.documento_id)):
        texto = open(f'{dir_txt}/{doc}.txt', encoding='utf-8').read()
        gold = [{'inicio': int(r.inicio), 'fim': int(r.fim),
                 'classificacao': r.classificacao,
                 'ids': set(str(r.id_canonico).split())
                        if isinstance(r.id_canonico, str) else set()}
                for r in g[g.documento_id == doc].itertuples()]
        spans = extrai(texto)
        preds = []
        for s in spans:
            classe, idc, _, diag = classifica(s, base)
            preds.append({'inicio': s['inicio'], 'fim': s['fim'],
                          'span': s, 'classe': classe, 'id': idc, 'diag': diag})
        pares, _ = alinha(gold, preds)
        casado = {j: i for i, j in pares}
        for j, p in enumerate(preds):
            i = casado.get(j)
            alvo = 0
            if i is not None:
                gi = gold[i]
                if gi['classificacao'] == p['classe']:
                    alvo = 1 if (p['classe'] != 'real' or str(p['id']) in gi['ids']) else 0
            X.append(vetor(p['span'], p['classe'], p['diag']))
            y.append(alvo)
            grupos.append(doc)
    return np.array(X, float), np.array(y, float), np.array(grupos)


def treina(X, y, l2=1.0, passos=4000, lr=0.5, alvo='brier'):
    """Regressao logistica, minimizando log-loss ou Brier.

    O bonus do desafio e medido por BRIER score, entao treinar direto nele e o
    alinhamento certo entre o que se otimiza e o que se pontua. Brier e regra
    de pontuacao propria: premia calibracao E discriminacao ao mesmo tempo.
    """
    w = np.zeros(X.shape[1])
    n = len(y)
    for _ in range(passos):
        p = 1.0 / (1.0 + np.exp(-np.clip(X @ w, -30, 30)))
        if alvo == 'brier':
            # d/dw media((p-y)^2) = media(2 (p-y) p (1-p) x)
            resid = 2.0 * (p - y) * p * (1.0 - p)
        else:
            resid = p - y
        grad = X.T @ resid / n + l2 * np.r_[0.0, w[1:]] / n
        w -= lr * grad
    return w


def ece(p, y, bins=10):
    """Erro de calibracao esperado: |confianca media - acerto medio| por faixa."""
    total = 0.0
    for k in range(bins):
        lo, hi = k / bins, (k + 1) / bins
        m = (p >= lo) & (p < hi if k < bins - 1 else p <= hi)
        if m.sum():
            total += m.sum() / len(p) * abs(p[m].mean() - y[m].mean())
    return total


def auc(p, y):
    """Area sob a ROC: mede DISCRIMINACAO, que a calibracao sozinha nao mede."""
    ordem = np.argsort(p)
    postos = np.empty(len(p), float)
    postos[ordem] = np.arange(1, len(p) + 1)
    n1, n0 = y.sum(), (1 - y).sum()
    if n1 == 0 or n0 == 0:
        return float('nan')
    return float((postos[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def relatorio(nome, p, y):
    brier = float(np.mean((p - y) ** 2))
    ll = float(-np.mean(y * np.log(np.clip(p, 1e-9, 1)) +
                        (1 - y) * np.log(np.clip(1 - p, 1e-9, 1))))
    print(f'   {nome:<24s} ECE {ece(p, y):.4f}   Brier {brier:.4f}   '
          f'logloss {ll:.4f}   AUC {auc(p, y):.4f}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sintetico', nargs='*',
                    default=['sintetico', 'sintetico_dificil'])
    ap.add_argument('--l2', type=float, default=1.0)
    ap.add_argument('--alvo', default='brier', choices=['brier', 'logloss'])
    a = ap.parse_args()
    base = BaseCanonica()

    Xg, yg, gg = amostras(base, 'dados/txt', 'dados/goldenset.csv')
    print(f'goldenset: {len(yg)} citacoes preditas, acerto medio {yg.mean():.1%}')
    Xs_all, ys_all, gs_all = [Xg], [yg], [gg]
    for d in a.sintetico:
        try:
            Xs, ys, gs = amostras(base, f'{d}/txt', f'{d}/goldenset.csv', id_str=True)
        except FileNotFoundError:
            print(f'{d}: ausente, ignorado'); continue
        print(f'{d}: {len(ys)} citacoes preditas, acerto medio {ys.mean():.1%}')
        Xs_all.append(Xs); ys_all.append(ys); gs_all.append(np.char.add(d + '/', gs))
    X = np.vstack(Xs_all); y = np.concatenate(ys_all); grupos = np.concatenate(gs_all)

    # validacao cruzada por documento
    docs = np.unique(grupos)
    rng = np.random.default_rng(0); rng.shuffle(docs)
    folds = np.array_split(docs, 5)
    p_cv = {}
    for alvo in ('logloss', 'brier'):
        p = np.zeros(len(y))
        for f in folds:
            teste = np.isin(grupos, f)
            w = treina(X[~teste], y[~teste], a.l2, alvo=alvo, lr=2.0 if alvo == 'brier' else 0.5,
                       passos=8000 if alvo == 'brier' else 4000)
            p[teste] = 1.0 / (1.0 + np.exp(-np.clip(X[teste] @ w, -30, 30)))
        p_cv[alvo] = p

    print('\nvalidacao cruzada por documento (5 folds):')
    relatorio('constante 0,90', np.full(len(y), 0.90), y)
    relatorio('tabela por forma+classe', tabela_por_forma(X, y), y)
    relatorio('logistica (log-loss)', p_cv['logloss'], y)
    relatorio('logistica (Brier)', p_cv['brier'], y)
    melhor = min(p_cv, key=lambda k: np.mean((p_cv[k] - y) ** 2))
    print(f'   -> menor Brier: treino por {melhor}')

    print('\ncurva de confiabilidade (modelo escolhido):')
    pm = p_cv[melhor]
    for k in range(10):
        lo, hi = k / 10, (k + 1) / 10
        m = (pm >= lo) & (pm < hi if k < 9 else pm <= hi)
        if m.sum():
            print(f'   [{lo:.1f},{hi:.1f})  n={m.sum():5d}  '
                  f'confianca {pm[m].mean():.3f}  acerto {y[m].mean():.3f}')

    w = treina(X, y, a.l2, alvo=melhor, lr=2.0 if melhor == 'brier' else 0.5,
               passos=8000 if melhor == 'brier' else 4000)
    corpo = ('# -*- coding: utf-8 -*-\n'
             '"""Gerado por calibra.py - NAO editar a mao."""\n\n'
             f'# Pesos da regressao logistica ({melhor}), na ordem de\n'
             '# cacador.features.NOMES.\n'
             'PESOS = [\n'
             + ''.join(f'    {v: .6f},  # {n}\n' for v, n in zip(w, NOMES))
             + ']\n')
    open('cacador/calibracao.py', 'w', encoding='utf-8').write(corpo)
    print(f'\ncacador/calibracao.py escrito ({len(w)} pesos)')


def tabela_por_forma(X, y):
    """Baseline: a media empirica por (forma, classe), como era antes."""
    chave = [tuple(linha[1:1 + 9]) for linha in X]
    soma = collections.Counter(); n = collections.Counter()
    for k, alvo in zip(chave, y):
        soma[k] += alvo; n[k] += 1
    return np.array([(soma[k] + 1) / (n[k] + 2) for k in chave])


if __name__ == '__main__':
    main()
