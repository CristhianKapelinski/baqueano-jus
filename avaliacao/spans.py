# -*- coding: utf-8 -*-
"""Lista os spans que o extrator perdeu e os que inventou, no conjunto pedido."""
import sys, collections
import pandas as pd

from .gabarito import carrega
from baqueano.canon import BaseCanonica
from baqueano.pipeline import processa_documento
from .metrica import DEV, HOLDOUT, alinha

conj = sys.argv[1] if len(sys.argv) > 1 else 'dev'
docs = {'dev': DEV, 'holdout': HOLDOUT, 'tudo': DEV + HOLDOUT}[conj]
base = BaseCanonica()
g = carrega()
perdidos, falsos = [], []
for doc in docs:
    texto = open(f'dados/txt/{doc}.txt', encoding='utf-8').read()
    gold = [{'inicio': int(r.inicio), 'fim': int(r.fim), 'trecho': r.trecho,
             'tipo': r.tipo, 'classificacao': r.classificacao}
            for r in g[g.documento_id == doc].itertuples()]
    pred = processa_documento(texto, base)['citacoes']
    pares, usados = alinha(gold, pred)
    casados = {i for i, _ in pares}
    for i, gi in enumerate(gold):
        if i not in casados:
            perdidos.append((doc, gi['tipo'], gi['classificacao'], repr(gi['trecho'])[:75]))
    for j, pj in enumerate(pred):
        if j not in usados:
            falsos.append((doc, pj['forma'], pj['classificacao'], repr(pj['trecho'])[:75]))
print(f'### PERDIDOS ({len(perdidos)})')
for p in perdidos: print('  ', p)
print(f'\n### FALSOS POSITIVOS ({len(falsos)})')
c = collections.Counter(f[1] for f in falsos)
print('   por forma:', dict(c))
for f in falsos: print('  ', f)
