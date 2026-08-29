# -*- coding: utf-8 -*-
"""Amostras rotuladas e ajuste logistico, compartilhados pelas ferramentas.

Isto era codigo de biblioteca escondido dentro de um script. Quem precisa
importa daqui; nenhum script importa de outro script.
"""
import pathlib

import numpy as np

from baqueano.classify import classifica
from baqueano.extract import extrai
from baqueano.features import vetor

from .gabarito import carrega, ids_aceitos
from .metrica import alinha


def amostras(base, dir_txt, csv, id_str=False):  # noqa: ARG001 - id_str herdado
    """Uma linha por PREDICAO do sistema, com o alvo 1 se ela seria pontuada.

    Falso positivo entra com alvo 0: uma predicao que nao existe no gabarito e
    um erro, e a confianca precisa aprender isso.
    """
    g = carrega(pathlib.Path(csv).parent)
    X, y, grupos = [], [], []
    for doc in sorted(set(g.documento_id)):
        texto = open(f'{dir_txt}/{doc}.txt', encoding='utf-8').read()
        gold = [{'inicio': int(r.inicio), 'fim': int(r.fim),
                 'classificacao': r.classificacao,
                 'ids': ids_aceitos(r)}
                for r in g[g.documento_id == doc].itertuples()]
        preds = []
        for s in extrai(texto):
            classe, idc, _, diag = classifica(s, base)
            preds.append({'inicio': s['inicio'], 'fim': s['fim'], 'span': s,
                          'classe': classe, 'id': idc, 'diag': diag})
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


def treina(X, y, l2=1.0, passos=4000, lr=0.5, alvo='logloss'):
    """Regressao logistica com L2, minimizando log-loss ou Brier.

    Treinar direto no Brier parece o alinhamento certo (a metrica do desafio e
    Brier), mas mede-se pior: o gradiente do Brier achata nos extremos. Por isso
    o alvo e um parametro e a escolha e feita por medicao, nao por principio.
    """
    w = np.zeros(X.shape[1])
    n = len(y)
    for _ in range(passos):
        p = 1.0 / (1.0 + np.exp(-np.clip(X @ w, -30, 30)))
        resid = 2.0 * (p - y) * p * (1.0 - p) if alvo == 'brier' else p - y
        w -= lr * (X.T @ resid / n + l2 * np.r_[0.0, w[1:]] / n)
    return w


def ece(p, y, faixas=10):
    """Erro de calibracao esperado: |confianca media - acerto medio| por faixa."""
    total = 0.0
    for k in range(faixas):
        lo, hi = k / faixas, (k + 1) / faixas
        m = (p >= lo) & (p < hi if k < faixas - 1 else p <= hi)
        if m.sum():
            total += m.sum() / len(p) * abs(p[m].mean() - y[m].mean())
    return float(total)


def auc(p, y):
    """Area sob a ROC: mede DISCRIMINACAO, que a calibracao sozinha nao mede."""
    ordem = np.argsort(p)
    postos = np.empty(len(p), float)
    postos[ordem] = np.arange(1, len(p) + 1)
    n1, n0 = y.sum(), (1 - y).sum()
    if n1 == 0 or n0 == 0:
        return float('nan')
    return float((postos[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def brier(p, y):
    return float(np.mean((p - y) ** 2))
