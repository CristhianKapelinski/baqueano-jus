# -*- coding: utf-8 -*-
"""Estima a confianca empirica por (forma, classe) e escreve cacador/calibracao.py.

A metrica da o bonus de calibracao a quem envia `confianca` bem ajustada. Em vez
de chutar um numero por tipo de evidencia, medimos a taxa de acerto de cada
combinacao (forma de extracao, classe decidida) no goldenset de desenvolvimento,
com suavizacao de Laplace para nao cravar 0 ou 1 em celula rara.
"""
import collections

import pandas as pd

from cacador.canon import BaseCanonica
from cacador.pipeline import processa_documento
from eval import DEV, HOLDOUT, alinha

ALFA = 1.0  # suavizacao


def main():
    base = BaseCanonica()
    g = pd.read_csv('dados/goldenset.csv')
    acerto = collections.Counter()
    total = collections.Counter()
    for doc in DEV + HOLDOUT:
        texto = open(f'dados/txt/{doc}.txt', encoding='utf-8').read()
        gold = [{'inicio': int(r.inicio), 'fim': int(r.fim),
                 'classificacao': r.classificacao,
                 'ids': set(str(r.id_canonico).split()) if isinstance(r.id_canonico, str) else set()}
                for r in g[g.documento_id == doc].itertuples()]
        pred = processa_documento(texto, base)['citacoes']
        pares, usados = alinha(gold, pred)
        casado = {j: i for i, j in pares}
        for j, p in enumerate(pred):
            chave = (p['forma'], p['classificacao'])
            total[chave] += 1
            i = casado.get(j)
            if i is None:
                continue
            gi = gold[i]
            if gi['classificacao'] != p['classificacao']:
                continue
            if p['classificacao'] == 'real':
                dado = (p.get('resolucao') or {}).get('id_canonico')
                if str(dado) not in gi['ids']:
                    continue
            acerto[chave] += 1
    linhas = []
    for chave in sorted(total):
        c = (acerto[chave] + ALFA) / (total[chave] + 2 * ALFA)
        linhas.append(f'    {chave!r}: {c:.4f},  # {acerto[chave]}/{total[chave]}')
    corpo = ('# -*- coding: utf-8 -*-\n'
             '"""Gerado por calibra.py - NAO editar a mao."""\n\n'
             '# (forma de extracao, classe) -> confianca empirica suavizada\n'
             'CONFIANCA = {\n' + '\n'.join(linhas) + '\n}\n'
             'PADRAO = 0.5\n')
    open('cacador/calibracao.py', 'w', encoding='utf-8').write(corpo)
    print(corpo)


if __name__ == '__main__':
    main()
