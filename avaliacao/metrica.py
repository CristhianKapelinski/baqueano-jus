# -*- coding: utf-8 -*-
"""Avaliacao local contra o goldenset.

O script oficial (kaggle_metric.py) nao veio no pacote de dados, entao este e
um proxy fiel ao que o enunciado descreve: alinhamento por IoU >= 0,5 sobre
spans em codepoints, e credito so quando a classe esta certa - e, nas `real`,
quando o id_canonico entregue esta no conjunto aceito. Nivel 1 pesa 1x,
nivel 2 pesa 2x.
"""
import argparse
import collections
import sys

import pandas as pd

from cacador.canon import BaseCanonica
from cacador.pipeline import processa_documento

DEV = [f'gen_n{n}_{i:03d}' for n in (1, 2) for i in range(1, 8)]
HOLDOUT = [f'gen_n{n}_{i:03d}' for n in (1, 2) for i in range(8, 14)]


def iou(a, b):
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    if inter == 0:
        return 0.0
    uniao = (a[1] - a[0]) + (b[1] - b[0]) - inter
    return inter / uniao


def alinha(gold, pred):
    """Casa gold com pred por IoU >= 0,5, guloso pelo melhor IoU."""
    pares, usados = [], set()
    cand = []
    for i, g in enumerate(gold):
        for j, p in enumerate(pred):
            v = iou((g['inicio'], g['fim']), (p['inicio'], p['fim']))
            if v >= 0.5:
                cand.append((v, i, j))
    cand.sort(reverse=True)
    vistos_g = set()
    for v, i, j in cand:
        if i in vistos_g or j in usados:
            continue
        vistos_g.add(i); usados.add(j)
        pares.append((i, j))
    return pares, usados


def avalia(docs, base, verboso=False):
    g = pd.read_csv('dados/goldenset.csv')
    tot = collections.Counter()
    peso_tot = peso_ok = 0.0
    mat = collections.Counter()
    erros = []
    for doc in docs:
        texto = open(f'dados/txt/{doc}.txt', encoding='utf-8').read()
        gold = [{'inicio': int(r.inicio), 'fim': int(r.fim), 'trecho': r.trecho,
                 'tipo': r.tipo, 'classificacao': r.classificacao,
                 'ids': set(str(r.id_canonico).split()) if isinstance(r.id_canonico, str) else set(),
                 'nivel': int(r.nivel)}
                for r in g[g.documento_id == doc].itertuples()]
        pred = processa_documento(texto, base)['citacoes']
        pares, usados = alinha(gold, pred)
        casados = {i for i, _ in pares}
        peso = 1 if gold and gold[0]['nivel'] == 1 else 2
        for i, gi in enumerate(gold):
            peso_tot += peso
            tot['gold'] += 1
            if i not in casados:
                tot['span_perdido'] += 1
                mat[(gi['classificacao'], 'AUSENTE')] += 1
                erros.append(('SPAN', doc, gi['classificacao'], gi['trecho'][:60]))
        for i, j in pares:
            gi, pj = gold[i], pred[j]
            mat[(gi['classificacao'], pj['classificacao'])] += 1
            if gi['classificacao'] != pj['classificacao']:
                erros.append(('CLASSE', doc, f"{gi['classificacao']}->{pj['classificacao']}",
                              gi['trecho'][:60]))
                continue
            if gi['classificacao'] == 'real':
                dado = (pj.get('resolucao') or {}).get('id_canonico')
                if str(dado) not in gi['ids']:
                    erros.append(('LINK', doc, f"deu {dado}, aceito {gi['ids']}",
                                  gi['trecho'][:60]))
                    continue
            tot['ok'] += 1
            peso_ok += peso
        tot['pred'] += len(pred)
        tot['falso_positivo'] += len(pred) - len(usados)
    return tot, peso_ok / peso_tot if peso_tot else 0.0, mat, erros


def relatorio(nome, docs, base, mostrar_erros=0):
    tot, escore, mat, erros = avalia(docs, base)
    rec = (tot['gold'] - tot['span_perdido']) / tot['gold']
    prec = (tot['pred'] - tot['falso_positivo']) / tot['pred'] if tot['pred'] else 0
    print(f'\n== {nome}  ({len(docs)} docs, {tot["gold"]} citacoes no gabarito)')
    print(f'   spans   : recall {rec:.1%}  precisao {prec:.1%}  '
          f'(preditos {tot["pred"]}, falsos positivos {tot["falso_positivo"]})')
    print(f'   corretas: {tot["ok"]}/{tot["gold"]}  ({tot["ok"]/tot["gold"]:.1%})')
    print(f'   ESCORE ponderado (n1=1x, n2=2x): {escore:.1%}')
    if mat:
        print('   gabarito -> predito')
        for real in ('real', 'inventada', 'incompleta'):
            linha = {p: mat[(real, p)] for p in ('real', 'inventada', 'incompleta', 'AUSENTE')
                     if mat[(real, p)]}
            print(f'     {real:11s} -> {linha}')
    if mostrar_erros:
        print('   --- erros ---')
        for e in erros[:mostrar_erros]:
            print('   ', e)
    return escore


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--conjunto', default='dev', choices=['dev', 'holdout', 'tudo'])
    ap.add_argument('--erros', type=int, default=0)
    a = ap.parse_args()
    base = BaseCanonica()
    docs = {'dev': DEV, 'holdout': HOLDOUT, 'tudo': DEV + HOLDOUT}[a.conjunto]
    relatorio(a.conjunto, docs, base, a.erros)
