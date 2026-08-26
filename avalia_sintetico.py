# -*- coding: utf-8 -*-
"""Avalia o pipeline num conjunto sintetico gerado por gerador.py."""
import argparse
import collections

import pandas as pd

from cacador.canon import BaseCanonica
from cacador.pipeline import processa_documento
from eval import alinha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='sintetico')
    ap.add_argument('--erros', type=int, default=0)
    a = ap.parse_args()
    base = BaseCanonica()
    g = pd.read_csv(f'{a.dir}/goldenset.csv', dtype={'id_canonico': str})
    docs = sorted(set(g.documento_id))
    tot = collections.Counter(); mat = collections.Counter()
    peso_t = peso_ok = 0.0
    por_forma = collections.Counter(); erros = []
    for doc in docs:
        texto = open(f'{a.dir}/txt/{doc}.txt', encoding='utf-8').read()
        gold = [{'inicio': int(r.inicio), 'fim': int(r.fim), 'trecho': str(r.trecho),
                 'classificacao': r.classificacao, 'nivel': int(r.nivel),
                 'ids': {str(r.id_canonico)} if isinstance(r.id_canonico, str) else set()}
                for r in g[g.documento_id == doc].itertuples()]
        pred = processa_documento(texto, base)['citacoes']
        pares, usados = alinha(gold, pred)
        casados = {i for i, _ in pares}
        peso = 1 if gold[0]['nivel'] == 1 else 2
        for i, gi in enumerate(gold):
            tot['gold'] += 1; peso_t += peso
            if i not in casados:
                tot['span_perdido'] += 1
                mat[(gi['classificacao'], 'AUSENTE')] += 1
                if len(erros) < 400:
                    erros.append(('SPAN', doc, gi['classificacao'], gi['trecho'][:70]))
        for i, j in pares:
            gi, pj = gold[i], pred[j]
            mat[(gi['classificacao'], pj['classificacao'])] += 1
            if gi['classificacao'] != pj['classificacao']:
                if len(erros) < 400:
                    erros.append(('CLASSE', doc,
                                  f"{gi['classificacao']}->{pj['classificacao']}",
                                  gi['trecho'][:70]))
                continue
            if gi['classificacao'] == 'real':
                if str((pj.get('resolucao') or {}).get('id_canonico')) not in gi['ids']:
                    if len(erros) < 400:
                        erros.append(('LINK', doc, '', gi['trecho'][:70]))
                    continue
            tot['ok'] += 1; peso_ok += peso
        tot['pred'] += len(pred); tot['fp'] += len(pred) - len(usados)
        for j, p in enumerate(pred):
            if j not in usados:
                por_forma[p['forma']] += 1
    print(f'{len(docs)} documentos, {tot["gold"]} citacoes')
    print(f'   spans   : recall {(tot["gold"]-tot["span_perdido"])/tot["gold"]:.1%}  '
          f'precisao {(tot["pred"]-tot["fp"])/tot["pred"]:.1%}  (fp {tot["fp"]})')
    print(f'   corretas: {tot["ok"]}/{tot["gold"]} ({tot["ok"]/tot["gold"]:.1%})')
    print(f'   ESCORE ponderado: {peso_ok/peso_t:.1%}')
    for real in ('real', 'inventada', 'incompleta'):
        print(f'     {real:11s} -> ' + str({p: mat[(real, p)] for p in
              ('real', 'inventada', 'incompleta', 'AUSENTE') if mat[(real, p)]}))
    print('   falsos positivos por forma:', dict(por_forma))
    if a.erros:
        c = collections.Counter((e[0], e[2]) for e in erros)
        print('\n   erros por tipo:')
        for k, n in c.most_common(15):
            print(f'     {n:4d}  {k}')
        print('\n   amostra:')
        for e in erros[:a.erros]:
            print('    ', e)


if __name__ == '__main__':
    main()
